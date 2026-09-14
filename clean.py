"""
Reads raw_scrape from scrape.duckdb, applies cleaning rules, writes clean_scrape.
Log: logs/clean.log
"""

import duckdb
import pandas as pd
import re
import logging
import sys
from pathlib import Path

db_path = "scrape.duckdb"
log_dir = Path("logs")
log_file = log_dir / "clean.log"

CATEGORY_MAP = {
    "legal": "Legal",
    "LEGAL": "Legal",
    "Lgl": "Legal",
    "Legal": "Legal",
    "ERP": "ERP",
    "HR": "HR",
    "Medical": "Medical",
    "MSP Platform": "MSP Platform",
    "LMS": "LMS",
}

NULL_STRINGS = {"nan", "none", "null", "n/a", "na", "nil", "","-"}

log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def is_null_string(value) -> bool:
    return value is None or str(value).strip().lower() in NULL_STRINGS


def clean_category(value):
    if is_null_string(value):
        return None
    stripped = str(value).strip()
    mapped = CATEGORY_MAP.get(stripped)
    if mapped is None:
        log.warning(f"unknown category value {stripped!r} -> Unknown")
        return "Unknown"
    return mapped


def clean_phone(value):
    """
    Spec: digits only, extensions stripped, leading 1 or 0 stripped, result is 10 digits.
    Returns (cleaned, flag) where flag is ok / invalid / null.
    """
    if is_null_string(value):
        return None, "null"

    # extensions show up as "ext. 12", "ext12", "x123", "#4" - cut those off
    # before stripping non-digits, otherwise the extension digits merge in
    no_ext = re.split(r"(?i)\s*(ext\.?|x\b|#)\s*\d+", str(value).strip())[0]
    digits = re.sub(r"\D", "", no_ext)

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    elif digits.startswith("0"):
        digits = digits[1:]

    if len(digits) == 10:
        return digits, "ok"
    return None, "invalid"


def clean_email(value):
    if is_null_string(value):
        return None, "null"
    cleaned = str(value).strip().lower()
    if "@" not in cleaned or "." not in cleaned:
        return cleaned, "invalid"
    return cleaned, "ok"


def clean_website(value):
    if is_null_string(value):
        return None
    return str(value).strip().lower()


TEXT_COLUMNS = [
    "scrape_date", "category", "company_name", "phone", "email", "website",
    "employee_count", "city", "country", "scraped_at", "source_url",
]


def apply_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    total = len(df)
    log.info(f"cleaning {total:,} rows")

    before = len(df)
    df = df[
        (df["category"] != "category")
        & (df["company_name"] != "company_name")
        & (df["scrape_date"] != "scrape_date")
    ]
    log.info(f"dropped {before - len(df)} junk header rows")

    for col in TEXT_COLUMNS:
        if col not in df.columns:
            continue
        df[col] = df[col].apply(lambda v: None if is_null_string(v) else str(v).strip())

    before_cats = df["category"].value_counts().to_dict()
    df["category"] = df["category"].apply(clean_category)
    log.info(f"category counts before: {before_cats}")
    log.info(f"category counts after : {df['category'].value_counts().to_dict()}")

    phone_results = df["phone"].apply(clean_phone)
    df["phone_clean"] = phone_results.apply(lambda x: x[0])
    df["phone_clean_flag"] = phone_results.apply(lambda x: x[1])
    log.info(f"phone flags: {df['phone_clean_flag'].value_counts().to_dict()}")
    log.info(f"sample invalid phones: {df[df['phone_clean_flag'] == 'invalid']['phone'].head(10).tolist()}")

    email_results = df["email"].apply(clean_email)
    df["email_clean"] = email_results.apply(lambda x: x[0])
    df["email_clean_flag"] = email_results.apply(lambda x: x[1])
    log.info(f"email flags: {df['email_clean_flag'].value_counts().to_dict()}")

    df["website_clean"] = df["website"].apply(clean_website)

    log.info(f"cleaning complete, {len(df):,} rows remain")
    return df


def print_summary(df: pd.DataFrame):
    log.info("=" * 60)
    log.info("CLEANING SUMMARY")
    log.info("=" * 60)
    log.info(f"total clean rows: {len(df):,}")

    log.info("category distribution:")
    for cat, count in df["category"].value_counts().items():
        log.info(f"  {cat:<20} {count:>7,}")

    log.info("phone flag distribution:")
    for flag, count in df["phone_clean_flag"].value_counts().items():
        log.info(f"  {flag:<20} {count:>7,}")

    log.info("email flag distribution:")
    for flag, count in df["email_clean_flag"].value_counts().items():
        log.info(f"  {flag:<20} {count:>7,}")

    key_cols = ["phone_clean", "email_clean", "website_clean", "city", "employee_count"]
    log.info("null counts after cleaning:")
    for col in key_cols:
        if col in df.columns:
            nulls = df[col].isna().sum()
            log.info(f"  {col:<20} {nulls:>7,} ({nulls / len(df) * 100:.1f}%)")

    sample = df[df["phone_clean_flag"] == "ok"][["phone", "phone_clean"]].head(10)
    log.info("sample cleaned phones:")
    for _, row in sample.iterrows():
        log.info(f"  {str(row['phone']):<30} -> {row['phone_clean']}")


def run_cleaning():
    log.info("=" * 60)
    log.info("CLEANING START")
    log.info("=" * 60)

    con = duckdb.connect(db_path)
    df = con.execute("select * from raw_scrape").df()
    log.info(f"loaded {len(df):,} rows from raw_scrape")

    df_clean = apply_cleaning(df)
    print_summary(df_clean)

    con.execute("drop table if exists clean_scrape")
    con.execute("create table clean_scrape as select * from df_clean")
    db_count = con.execute("select count(*) from clean_scrape").fetchone()[0]
    log.info(f"wrote {db_count:,} rows to clean_scrape")
    con.close()

    log.info("=" * 60)
    log.info("CLEANING COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    run_cleaning()
