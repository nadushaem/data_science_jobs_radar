# выгрузка недели на ручную разметку и импорт разметки в eval/gold_<версия>.csv
# запуск из корня репозитория, export — на копии серверной базы:
#   $env:DB_PATH = "data/radar_server.db"
#   python -m eval.labeling export --gold v2 --since 2026-10-11 --until 2026-10-18
#   python -m eval.labeling import --gold v2
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from eval.evaluate import split_keys
from pipeline.dedupe import _company_key
from storage.vacancies import load_raw_vacancies

DEV = "v1"  # dev-разметка: из нее подмешиваем строки для слепой переразметки
SHEET_COLUMNS = ["url", "source", "company", "title", "description"]
LABEL_COLUMNS = ["ds_role", "roles", "industries", "industry_other", "unsure", "comment"]
MAX_DESCRIPTION = 3000


# «та же компания + то же название». без компании ключ — url,
# иначе слились бы одинаковые названия у разных скрытых работодателей
def repost_key(df):
    company = df["company"].map(_company_key)
    title = df["title"].fillna("").str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
    return (company + "|" + title).where(company != "", df["url"])


# роль определяется только по названию, поэтому повтор компании + названия — тот же пример:
# из dev он дал бы утечку, внутри недели — ложно узкие бутстрэп-интервалы
def select_test(raw, dev_snapshot):
    keys = repost_key(raw)
    in_dev = raw["url"].isin(dev_snapshot["url"]) | keys.isin(repost_key(dev_snapshot))
    repost = keys.duplicated() & ~in_dev  # raw отсортирован по first_seen_at: остается первая
    print(f"за окно: {len(raw)}, пересекаются с {DEV}: {in_dev.sum()}, перепосты: {repost.sum()}")
    return raw[~in_dev & ~repost].reset_index(drop=True)


# лист без предсказаний классификатора, в случайном порядке, со ссылками
def write_sheet(df, path):
    df = df[SHEET_COLUMNS].assign(**dict.fromkeys(LABEL_COLUMNS, None))
    text = df[SHEET_COLUMNS].fillna("").astype(str)  # управляющие символы из html excel не сохранит
    df[SHEET_COLUMNS] = text.replace(ILLEGAL_CHARACTERS_RE, "", regex=True)
    df["description"] = df["description"].str.slice(0, MAX_DESCRIPTION)
    df.to_excel(path, index=False, sheet_name="labels")

    wb = load_workbook(path)
    ws = wb.active
    ws.freeze_panes, ws.auto_filter.ref = "A2", ws.dimensions  # сортировка фильтром не тронет шапку
    for cell in ws["A"][1:]:
        cell.hyperlink, cell.style = cell.value, "Hyperlink"
    for column, width in zip("ABCDE", [30, 10, 25, 50, 60], strict=True):
        ws.column_dimensions[column].width = width
    wb.save(path)


def export(gold, since, until, n_recheck, seed=42):
    sheet_path = Path(f"data/eval/to_label_{gold}.xlsx")
    snapshot_path = Path(f"data/eval/snapshot_{gold}.pkl")
    if sheet_path.exists() or snapshot_path.exists():
        sys.exit(f"{sheet_path} или {snapshot_path} уже есть — не перезаписываю разметку")

    dev_snapshot = pd.read_pickle(f"data/eval/snapshot_{DEV}.pkl")
    test = select_test(load_raw_vacancies(since, until), dev_snapshot)
    if test.empty:
        sys.exit("за это окно вакансий нет — проверь DB_PATH и даты")
    test.to_pickle(snapshot_path)  # заморозка: копия базы потом перезапишется

    # поровну DS и не-DS: на 5 позитивах kappa ни о чем не скажет
    dev_gold = pd.read_csv(f"eval/gold_{DEV}.csv", encoding="utf-8-sig")
    dev_gold = dev_gold[dev_gold["unsure"].fillna(0) == 0]
    picked = dev_gold.groupby("ds_role").sample(n_recheck // 2, random_state=seed)["url"]
    recheck = dev_snapshot[dev_snapshot["url"].isin(picked)]

    write_sheet(pd.concat([test, recheck]).sample(frac=1, random_state=seed), sheet_path)
    print(f"на разметку {len(test) + len(recheck)}: {len(test)} новых + {len(recheck)} из {DEV}")
    print(test["source"].value_counts().to_dict(), f"-> {sheet_path}")


def cohen_kappa(a, b):
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    expected = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return ((a == b).mean() - expected) / (1 - expected)


# согласие с собой: те же вакансии из dev, размеченные вслепую второй раз
def report_agreement(dev_gold, recheck):
    df = dev_gold.merge(recheck, on="url", suffixes=("_dev", "_re"))
    df = df[(df["unsure_dev"].fillna(0) == 0) & (df["unsure_re"].fillna(0) == 0)]
    a, b = df["ds_role_dev"].astype(bool), df["ds_role_re"].astype(bool)
    both = df[a & b]
    same_roles = (both["roles_dev"].map(split_keys) == both["roles_re"].map(split_keys)).mean()
    print(f"переразметка {DEV}: n = {len(df)}, ds_role совпал {(a == b).mean():.0%}")
    print(f"kappa = {cohen_kappa(a, b):.2f}, roles совпали в {same_roles:.0%} из {len(both)}")


def import_labels(gold):
    sheet = pd.read_excel(f"data/eval/to_label_{gold}.xlsx", dtype=str)[["url", *LABEL_COLUMNS]]
    sheet = sheet.apply(lambda column: column.str.strip())
    unlabeled = sheet.loc[sheet["ds_role"].isna(), "url"]
    if len(unlabeled):
        sys.exit(f"не размечено {len(unlabeled)}: {unlabeled.head(10).tolist()}")
    for column in ["ds_role", "unsure"]:  # «1.0» из excel → 1
        sheet[column] = pd.to_numeric(sheet[column]).astype("Int64")

    dev_gold = pd.read_csv(f"eval/gold_{DEV}.csv", encoding="utf-8-sig")
    is_recheck = sheet["url"].isin(dev_gold["url"])
    test, recheck = sheet[~is_recheck], sheet[is_recheck]
    test.sort_values("url").to_csv(f"eval/gold_{gold}.csv", index=False, encoding="utf-8-sig")
    recheck.sort_values("url").to_csv(f"eval/recheck_{DEV}.csv", index=False, encoding="utf-8-sig")
    print(f"{gold}: {len(test)} вакансий, из них с DS-ролью {test['ds_role'].sum()}")
    report_agreement(dev_gold, recheck)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("--gold", default="v2", help="версия разметки")
    parser.add_argument("--since", help="начало окна по first_seen_at, YYYY-MM-DD")
    parser.add_argument("--until", help="конец окна, не включая")
    parser.add_argument("--recheck", type=int, default=50, help="строк из dev для переразметки")
    args = parser.parse_args()

    if args.action == "import":
        import_labels(args.gold)
    elif not (args.since and args.until):
        parser.error("для export нужны --since и --until")
    else:
        export(args.gold, args.since, args.until, args.recheck)


if __name__ == "__main__":
    main()
