# оценка классификатора на gold set
# запуск из корня репозитория: python -m eval.evaluate [--gold v1] [--rev <ревизия>]
import argparse
import subprocess
import sys

import numpy as np
import pandas as pd

from pipeline import keywords
from pipeline.classify import classify_vacancies
from pipeline.normalize import normalize_dataframe

N_BOOTSTRAP = 1000
# наивный baseline: в заголовке есть data / ml / ai
NAIVE_PATTERN = r"\b(?:data|ml|ai)\b|дата|данных"
ERROR_COLUMNS = [
    "error",
    "company",
    "title",
    "roles",
    "matched_roles",
    "industries",
    "ind_pred",
    "url",
]


# таксономия из рабочей копии или из любой ревизии git — для истории «до/после».
# код классификатора при этом текущий, меняются только словари
def load_taxonomy(rev=None):
    if rev is None:
        return vars(keywords)
    command = ["git", "show", f"{rev}:pipeline/keywords.py"]
    source = subprocess.run(command, capture_output=True, encoding="utf-8", check=True).stdout
    namespace = {}
    exec(source, namespace)  # свой же файл из истории репозитория, внутри только словари
    return namespace


def split_keys(value):
    if pd.isna(value):
        return set()
    return {key.strip() for key in str(value).split("|") if key.strip()}


# метрики на грязной разметке ничего не значат — сначала проверяем схему
def validate_gold(gold):
    role_keys = {*keywords.ROLE_TAXONOMY, "other"}
    industry_keys = set(keywords.TARGET_KEYWORDS)
    problems = [f"{url}: дубль url" for url in gold.loc[gold["url"].duplicated(), "url"]]

    for row in gold.itertuples():
        unknown = (row.roles - role_keys) | (row.industries - industry_keys)
        if unknown:
            problems.append(f"{row.url}: неизвестные ключи {sorted(unknown)}")
        if row.ds_role and not row.roles:
            problems.append(f"{row.url}: ds_role = 1, но roles пустые")
        if not row.ds_role and (row.roles or row.industries):
            problems.append(f"{row.url}: ds_role = 0, но заполнены roles / industries")

    if problems:
        sys.exit("ошибки в разметке:\n" + "\n".join(problems))


def load_gold(path):
    gold = pd.read_csv(path, encoding="utf-8-sig")
    missing = gold["ds_role"].isna()
    if missing.any():
        sys.exit(f"не размечен ds_role: {gold.loc[missing, 'url'].tolist()}")

    gold["ds_role"] = gold["ds_role"].astype(bool)
    gold["unsure"] = gold["unsure"].fillna(0).astype(bool)
    for column in ["roles", "industries"]:
        gold[column] = gold[column].map(split_keys)
    validate_gold(gold)

    # is_target не размечается — выводим так же, как classify.py
    gold["is_target"] = gold["ds_role"] & gold["industries"].map(bool)
    return gold


# тот же путь, что в main.py, но без дедупа: метрики считаем на уровне вакансий
def predict(snapshot, taxonomy):
    df = normalize_dataframe(snapshot.replace(r"^\s*$", pd.NA, regex=True))
    keys = ("TARGET_KEYWORDS", "ROLE_TAXONOMY", "EXCLUDED_ROLES")
    records = classify_vacancies(df.to_dict("records"), *(taxonomy[key] for key in keys))
    categories = list(taxonomy["TARGET_KEYWORDS"])

    pred = pd.DataFrame(records)
    pred["role_pred"] = pred["matched_roles"].map(bool) & ~pred["excluded_roles"].map(bool)
    pred["naive_pred"] = pred["title"].fillna("").str.contains(NAIVE_PATTERN)
    pred["ind_pred"] = [{key for key in categories if row[key]} for row in records]
    return pred.rename(columns={"is_target": "target_pred"})


def prf(y_true, y_pred):
    tp, n_pred, n_true = (y_true & y_pred).sum(), y_pred.sum(), y_true.sum()
    precision = tp / n_pred if n_pred else np.nan
    recall = tp / n_true if n_true else np.nan
    f1 = 2 * tp / (n_pred + n_true) if n_pred + n_true else np.nan
    return precision, recall, f1


# точка + 95% бутстрэп-интервал. seed общий, поэтому версии таксономии
# сравниваются на одних и тех же ресемплах (парное сравнение)
def report(name, y_true, y_pred, seed=42):
    y_true, y_pred = np.asarray(y_true, dtype=bool), np.asarray(y_pred, dtype=bool)
    idx = np.random.default_rng(seed).integers(0, len(y_true), (N_BOOTSTRAP, len(y_true)))
    point = prf(y_true, y_pred)
    samples = [prf(y_true[i], y_pred[i]) for i in idx]
    low, high = np.nanpercentile(samples, [2.5, 97.5], axis=0)

    cells = [f"{p:.2f} [{lo:.2f}, {hi:.2f}]" for p, lo, hi in zip(point, low, high, strict=True)]
    tp, fp, fn = (y_true & y_pred).sum(), (~y_true & y_pred).sum(), (y_true & ~y_pred).sum()
    print(f"{name:<24} P {cells[0]}  R {cells[1]}  F1 {cells[2]}  tp/fp/fn {tp}/{fp}/{fn}")


# сферы условные: насколько точно определяется сфера у DS-вакансий
def report_industries(ds):
    print("\n=== сферы (только ds_role = 1) ===")
    true_all, pred_all = [], []

    for key in keywords.TARGET_KEYWORDS:
        y_true = [key in keys for keys in ds["industries"]]
        y_pred = [key in keys for keys in ds["ind_pred"]]
        if any(y_true) or any(y_pred):
            report(key, y_true, y_pred)
        true_all += y_true
        pred_all += y_pred

    report("micro", true_all, pred_all)


# ошибки — главный вход для следующей итерации таксономии
def save_errors(df, path):
    df = df.assign(error="")
    df.loc[df["is_target"] != df["target_pred"], "error"] = "industry"
    df.loc[~df["ds_role"] & df["role_pred"], "error"] = "fp_role"
    df.loc[df["ds_role"] & ~df["role_pred"], "error"] = "fn_role"

    errors = df[df["error"] != ""].sort_values(["error", "company"])
    errors[ERROR_COLUMNS].to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nошибки {errors['error'].value_counts().to_dict()} -> {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="v1", help="версия gold set: v1 — dev, v2 — test")
    parser.add_argument("--rev", help="ревизия git для keywords.py, по умолчанию рабочая копия")
    args = parser.parse_args()

    gold = load_gold(f"eval/gold_{args.gold}.csv")
    pred = predict(pd.read_pickle(f"data/eval/snapshot_{args.gold}.pkl"), load_taxonomy(args.rev))
    df = gold.merge(pred, on="url", how="inner")
    print(f"gold: {len(gold)}, снапшот: {len(pred)}, совпало по url: {len(df)}")
    print(f"unsure: {df['unsure'].sum()} — в метрики не идут")
    df = df[~df["unsure"]]

    print(f"\n=== gold {args.gold}, таксономия: {args.rev or 'рабочая копия'} ===")
    report("ds_role: правила", df["ds_role"], df["role_pred"])
    report("ds_role: naive baseline", df["ds_role"], df["naive_pred"])
    report("is_target", df["is_target"], df["target_pred"])
    report_industries(df[df["ds_role"]])
    save_errors(df, f"data/eval/errors_{args.gold}.csv")


if __name__ == "__main__":
    main()
