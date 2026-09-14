"""
Output:
    - scrape.duckdb  (database file with raw_scrape table)
    - logs/ingest.log (log of every file loaded and any issues found)
"""

import duckdb
import pandas as pd
import os
import logging
import sys
from pathlib import Path
from datetime import datetime


# CONFIG

DAILY_DIR = Path("daily")          # folder containing the 42 CSV files
DB_PATH = "scrape.duckdb"          # output DuckDB database
LOG_DIR = Path("logs")             # folder for log files
LOG_FILE = LOG_DIR / "ingest.log"


EXPECTED_COLUMNS = [
    "scrape_date",
    "category",
    "company_name",
    "phone",
    "email",
    "website",
    "employee_count",
    "city",
    "country",
    "scraped_at",
]

# LOGGING SETUP

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)



# HELPER FUNCTIONS

def extract_date_from_filename(filepath: Path) -> str | None:
    """
    Pull the scrape date out of the filename.
    Expected format: scrape_2026-06-01.csv  →  '2026-06-01'
    Returns None if the filename doesn't match the expected pattern.
    """
    name = filepath.stem  # 'scrape_2026-06-01'
    parts = name.split("_", 1)
    if len(parts) == 2:
        return parts[1]  # '2026-06-01'
    return None


def safe_read_csv(filepath: Path) -> pd.DataFrame | None:

    encodings_to_try = ["utf-8", "latin-1", "cp1252"]

    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(
                filepath,
                dtype=str,           # read everything as string - clean later
                encoding=encoding,
                on_bad_lines="warn", # skip malformed rows but keep going
                skip_blank_lines=True,
            )

            if df.empty:
                log.warning(f"[EMPTY FILE] {filepath.name} - no rows after header")
                return pd.DataFrame(columns=EXPECTED_COLUMNS)

            log.info(f"[READ OK] {filepath.name} | encoding={encoding} | rows={len(df)} | cols={list(df.columns)}")
            return df

        except UnicodeDecodeError:
            # Try the next encoding
            continue
        except pd.errors.EmptyDataError:
            log.warning(f"[EMPTY FILE] {filepath.name} - file has no content at all")
            return pd.DataFrame(columns=EXPECTED_COLUMNS)
        except Exception as e:
            log.error(f"[READ ERROR] {filepath.name} | {type(e).__name__}: {e}")
            return None

    log.error(f"[ENCODING FAIL] {filepath.name} - could not decode with any known encoding")
    return None


def normalise_columns(df: pd.DataFrame, filepath: Path) -> pd.DataFrame:

    # Clean up column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    actual_cols = set(df.columns)
    expected_cols = set(EXPECTED_COLUMNS)

    extra = actual_cols - expected_cols
    missing = expected_cols - actual_cols

    if extra:
        log.warning(f"[EXTRA COLS] {filepath.name} has unexpected columns: {sorted(extra)}")

    if missing:
        log.warning(f"[MISSING COLS] {filepath.name} is missing expected columns: {sorted(missing)}")
        for col in missing:
            df[col] = None  # add as empty column

    return df


def add_metadata(df: pd.DataFrame, filepath: Path, file_date: str | None) -> pd.DataFrame:
    """
    Add two metadata columns to every row:
      - _source_file : which CSV file this row came from
      - _file_date   : date extracted from the filename

    Also: if scrape_date column is completely empty/missing,
    fill it from the filename date (best effort).
    """
    df["_source_file"] = filepath.name
    df["_file_date"] = file_date

    # If scrape_date is missing or all null, use filename date as fallback
    if "scrape_date" in df.columns:
        null_count = df["scrape_date"].isna().sum()
        if null_count == len(df) and file_date:
            log.warning(
                f"[DATE FALLBACK] {filepath.name} - scrape_date is all null, "
                f"filling from filename: {file_date}"
            )
            df["scrape_date"] = file_date

    return df



# MAIN INGESTION FUNCTION

def run_ingestion():
    log.info("=" * 60)
    log.info("INGESTION START")
    log.info(f"Looking for CSV files in: {DAILY_DIR.resolve()}")
    log.info(f"Output database: {DB_PATH}")
    log.info("=" * 60)

    # 1. Find all CSV files
    if not DAILY_DIR.exists():
        log.error(f"daily/ folder not found at {DAILY_DIR.resolve()}")
        log.error("Make sure you run this script from your project root folder.")
        sys.exit(1)

    csv_files = sorted(DAILY_DIR.glob("*.csv"))

    if not csv_files:
        log.error("No CSV files found in daily/ folder.")
        sys.exit(1)

    log.info(f"Found {len(csv_files)} CSV files to process")

    # 2. Read and combine all files
    all_frames = []
    files_ok = 0
    files_failed = 0

    for filepath in csv_files:
        file_date = extract_date_from_filename(filepath)

        if file_date is None:
            log.warning(f"[BAD FILENAME] {filepath.name} - cannot extract date, will use NULL")

        df = safe_read_csv(filepath)

        if df is None:
            log.error(f"[SKIPPED] {filepath.name} - could not be read")
            files_failed += 1
            continue

        df = normalise_columns(df, filepath)
        df = add_metadata(df, filepath, file_date)
        all_frames.append(df)
        files_ok += 1

    log.info("-" * 60)
    log.info(f"Files loaded successfully : {files_ok}")
    log.info(f"Files failed/skipped      : {files_failed}")

    if not all_frames:
        log.error("No data loaded at all - nothing to write to database.")
        sys.exit(1)

    # 3. Combine into one DataFrame
    log.info("Combining all files into a single table...")
    combined = pd.concat(all_frames, ignore_index=True)
    log.info(f"Total rows combined: {len(combined)}")
    log.info(f"Total columns      : {list(combined.columns)}")

    # 4. Basic null report before writing
    log.info("Null counts per column:")
    for col in combined.columns:
        null_count = combined[col].isna().sum()
        pct = (null_count / len(combined)) * 100
        if null_count > 0:
            log.info(f"  {col:<20} {null_count:>6} nulls  ({pct:.1f}%)")

    # 5. Write to DuckDB
    log.info(f"Writing to DuckDB: {DB_PATH}")

    con = duckdb.connect(DB_PATH)

    # Drop and recreate table so re-runs are safe
    con.execute("DROP TABLE IF EXISTS raw_scrape")

    con.execute("""
        CREATE TABLE raw_scrape AS
        SELECT * FROM combined
    """)

    # Verify row count in DB matches what we loaded
    db_count = con.execute("SELECT COUNT(*) FROM raw_scrape").fetchone()[0]
    log.info(f"Rows written to raw_scrape table: {db_count}")

    if db_count != len(combined):
        log.error(
            f"ROW COUNT MISMATCH! DataFrame had {len(combined)} rows "
            f"but DB has {db_count} rows."
        )
    else:
        log.info("Row count verified OK.")

    # 6. Preview
    log.info("Sample of first 3 rows in DB:")
    sample = con.execute("SELECT * FROM raw_scrape LIMIT 3").df()
    log.info(f"\n{sample.to_string()}")

    con.close()

    log.info("=" * 60)
    log.info("INGESTION COMPLETE")
    log.info(f"Database saved to : {DB_PATH}")
    log.info(f"Log saved to      : {LOG_FILE}")
    log.info("=" * 60)




if __name__ == "__main__":
    run_ingestion()