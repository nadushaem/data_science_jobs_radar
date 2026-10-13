# запуск из корня репозитория: python -m eval.evaluate_dedupe [--gold v1] [--rev <ревизия>]
# снапшот делается один раз, из копии серверной базы:
#   $env:DB_PATH = "data/radar_server.db"; python -m eval.evaluate_dedupe --freeze
import argparse
import re
import subprocess
import sys
import types
from pathlib import Path

import pandas as pd

from eval.evaluate import report
from pipeline import dedupe
from pipeline.normalize import normalize_dataframe
from storage.vacancies import load_raw_vacancies

GOLD_COLUMNS = ["source_a", "title_a", "url_a", "source_b", "title_b", "url_b", "is_dup"]
ERROR_COLUMNS = ["error", "company", "source_a", "title_a", "source_b", "title_b", "url_a", "url_b"]


# dedupe.py из рабочей копии или из любой ревизии git: main, ветка, тег.
# так все версии правила считаются на одном снапшоте одним и тем же кодом оценки
def load_dedupe(rev=None):
    if rev is None:
        return dedupe
    command = ["git", "show", f"{rev}:pipeline/dedupe.py"]
    source = subprocess.run(command, capture_output=True, encoding="utf-8", check=True).stdout
    module = types.ModuleType("dedupe_rev")
    exec(source, module.__dict__)  # свой же файл из истории репозитория
    return module


def load_gold(path):
    gold = pd.read_csv(path, encoding="utf-8-sig")
    if gold["is_dup"].isna().any():
        sys.exit(f"не размечен is_dup: строки {gold.index[gold['is_dup'].isna()].tolist()}")

    gold["is_dup"] = gold["is_dup"].astype(bool)
    gold["unsure"] = gold["unsure"].fillna(0).astype(bool)
    # одна и та же пара в двух строках исказит метрики
    pairs = gold[["url_a", "url_b"]].apply(frozenset, axis=1)
    if pairs.duplicated().any():
        sys.exit(f"повторы пар: {gold.loc[pairs.duplicated(), GOLD_COLUMNS].to_string()}")
    return gold


# копия базы перезапишется при следующем scp, а метрики должны считаться
# на тех же вакансиях, на которых размечены пары. поэтому замораживаем сырой слой
def freeze(gold, path):
    raw = load_raw_vacancies("2000-01-01", "2100-01-01")  # копия базы — уже срез, берём целиком
    missing = (set(gold["url_a"]) | set(gold["url_b"])) - set(raw.get("url", []))
    if missing:
        sys.exit(f"в базе нет {len(missing)} вакансий из разметки — проверь DB_PATH")

    path.parent.mkdir(parents=True, exist_ok=True)
    raw.to_pickle(path)
    print(f"снапшот: {len(raw)} вакансий -> {path}")


# тот же путь, что в main.py: дедуп по всему снапшоту, а не по размеченным парам —
# от снапшота зависят фильтр шаблонного текста и порядок склейки.
# пара считается склеенной, если обе вакансии попали в одну оставленную версию
def predict_clusters(snapshot, module):
    df = normalize_dataframe(snapshot.replace(r"^\s*$", pd.NA, regex=True))
    result = module.deduplicate_vacancies(df)

    cluster = dict(zip(result["url"], result["url"], strict=True))
    for url, duplicates in zip(result["url"], result["duplicate_urls"], strict=True):
        cluster |= dict.fromkeys(duplicates, url)
    return cluster


def save_errors(df, path):
    errors = df[df["is_dup"] != df["pred"]].copy()
    errors["error"] = errors["is_dup"].map({True: "fn", False: "fp"})
    errors.sort_values(["error", "company"])[ERROR_COLUMNS].to_csv(
        path, index=False, encoding="utf-8-sig"
    )
    print(f"\nошибки {errors['error'].value_counts().to_dict()} -> {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="v1", help="версия разметки: v1 — dev, v2 — test")
    parser.add_argument("--rev", help="ревизия git для dedupe.py, по умолчанию рабочая копия")
    parser.add_argument("--freeze", action="store_true", help="сохранить снапшот из DB_PATH")
    args = parser.parse_args()

    gold = load_gold(f"eval/dedupe_gold_{args.gold}.csv")
    snapshot_path = Path(f"data/eval/dedupe_snapshot_{args.gold}.pkl")
    if args.freeze:
        freeze(gold, snapshot_path)
        return

    cluster = predict_clusters(pd.read_pickle(snapshot_path), load_dedupe(args.rev))
    pairs = zip(gold["url_a"], gold["url_b"], strict=True)
    gold["pred"] = [cluster.get(a, a) == cluster.get(b, b) for a, b in pairs]
    gold["cross"] = gold["source_a"] != gold["source_b"]
    # наивный baseline: одинаковые названия у одной компании
    gold["naive"] = gold["title_a"] == gold["title_b"]

    print(f"пар: {len(gold)}, unsure: {gold['unsure'].sum()} — в метрики не идут")
    df = gold[~gold["unsure"]]
    print(f"дублей: {df['is_dup'].sum()}, разные борды: {df['cross'].sum()}")

    print(f"\n=== dedupe {args.gold}, правило: {args.rev or 'рабочая копия'} ===")
    report("все пары", df["is_dup"], df["pred"])
    report("разные борды", df.loc[df["cross"], "is_dup"], df.loc[df["cross"], "pred"])
    report("один борд", df.loc[~df["cross"], "is_dup"], df.loc[~df["cross"], "pred"])
    report("naive baseline", df["is_dup"], df["naive"])

    rev_name = re.sub(r"\W+", "_", args.rev or "worktree")
    save_errors(df, f"data/eval/dedupe_errors_{args.gold}_{rev_name}.csv")


if __name__ == "__main__":
    main()
