"""
Stage 3 - entity resolution.
Collapses clean_scrape rows down to one row per real company.

Priority order: exact phone_clean match, then exact domain match, then a fuzzy
company-name match. Whichever tier matches first wins - so if two rows share a
phone but have different names, they still merge as one entity (phone outranks
name), and it gets logged as a conflict rather than silently merged.

Writes entity_map.csv (entity_id, canonical_name, canonical_phone, categories,
n_raw_rows) and an entity_map table in scrape.duckdb.
"""

import re
import sys
import logging
from pathlib import Path
from difflib import SequenceMatcher

import duckdb
import pandas as pd

DB_PATH = "scrape.duckdb"
OUTPUT_CSV = "entity_map.csv"
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "entity_resolution.log"

# "Cedar FinHub" vs "Cedar Fin Hub" scores ~0.96 here, which is why 0.90 was picked
NAME_SIMILARITY_THRESHOLD = 0.90

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


def extract_domain(website):
    if not website or pd.isna(website):
        return None
    domain = re.sub(r"^https?://", "", str(website).strip().lower())
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0].split(":")[0]
    return domain or None


def normalise_name(name):
    if not name:
        return ""
    n = str(name).lower().strip()
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"\s+", " ", n)
    return n


def fuzzy_group_names(names: pd.Series, next_id: int):
    """
    Incremental clustering: walk the names once, compare each to the
    representative name of every cluster seen so far, join the first one
    that's close enough, otherwise start a new cluster.

    O(n * clusters) rather than a full O(n^2) pairwise comparison - fine as
    long as this pool stays small, which it does here since a row only reaches
    this tier when it has neither a phone nor a domain to match on.
    """
    ids = pd.Series(pd.NA, index=names.index, dtype="Int64")
    clusters = []  # (representative_name, entity_id)
    for idx, name in names.items():
        found = next(
            (eid for rep, eid in clusters if SequenceMatcher(None, name, rep).ratio() >= NAME_SIMILARITY_THRESHOLD),
            None,
        )
        if found is None:
            found = next_id
            clusters.append((name, found))
            next_id += 1
        ids[idx] = found
    return ids, next_id


def assign_entities(df: pd.DataFrame) -> pd.Series:
    entity_id = pd.Series(pd.NA, index=df.index, dtype="Int64")
    next_id = 1

    has_phone = df["phone_clean"].notna()
    codes, _ = pd.factorize(df.loc[has_phone, "phone_clean"])
    entity_id.loc[has_phone] = codes + next_id
    next_id += (codes.max() + 1) if len(codes) else 0
    log.info(f"phone match: {has_phone.sum():,} rows -> {codes.max() + 1 if len(codes) else 0:,} entities")

    remaining = entity_id.isna()
    has_domain = remaining & df["domain"].notna()
    codes, _ = pd.factorize(df.loc[has_domain, "domain"])
    entity_id.loc[has_domain] = codes + next_id
    next_id += (codes.max() + 1) if len(codes) else 0
    log.info(f"domain match (phone missing): {has_domain.sum():,} rows -> {codes.max() + 1 if len(codes) else 0:,} entities")

    remaining = entity_id.isna()
    log.info(f"no phone or domain, falling back to name match: {remaining.sum():,} rows")
    if remaining.any():
        name_ids, next_id = fuzzy_group_names(df.loc[remaining, "normalised_name"], next_id)
        entity_id.loc[remaining] = name_ids

    still_missing = entity_id.isna()
    if still_missing.any():
        # no name either - nothing left to group on, each gets its own entity
        entity_id.loc[still_missing] = range(next_id, next_id + still_missing.sum())

    log.info(f"total entities: {entity_id.nunique():,}")
    return entity_id


def build_entity_map(df: pd.DataFrame, entity_id: pd.Series) -> pd.DataFrame:
    df = df.assign(entity_id=entity_id)

    records = []
    conflicts = []

    for eid, group in df.groupby("entity_id"):
        name_counts = group["company_name"].dropna().value_counts()
        phone_counts = group["phone_clean"].dropna().value_counts()

        canonical_name = name_counts.index[0] if len(name_counts) else None
        canonical_phone = phone_counts.index[0] if len(phone_counts) else None
        categories = "|".join(sorted(group["category"].dropna().unique()))

        unique_phones = group["phone_clean"].dropna().nunique()
        unique_domains = group["domain"].dropna().nunique()
        unique_names = group["company_name"].dropna().nunique()

        # a group only ends up with >1 of any of these when a lower-priority
        # signal disagreed with the one that actually formed the group
        if unique_phones > 1 or unique_domains > 1 or unique_names > 1:
            conflicts.append({
                "entity_id": eid,
                "canonical_name": canonical_name,
                "unique_phones": unique_phones,
                "unique_domains": unique_domains,
                "unique_names": unique_names,
                "n_raw_rows": len(group),
            })

        records.append({
            "entity_id": eid,
            "canonical_name": canonical_name,
            "canonical_phone": canonical_phone,
            "categories": categories,
            "n_raw_rows": len(group),
            "first_seen": group["scrape_date"].dropna().min(),
        })

    entity_map = pd.DataFrame(records)

    log.info(f"entities: {len(entity_map):,}, with conflicting signals: {len(conflicts):,}")
    for c in conflicts[:5]:
        log.info(
            f"  conflict entity_id={c['entity_id']} name={c['canonical_name']!r} "
            f"unique_phones={c['unique_phones']} unique_domains={c['unique_domains']} "
            f"unique_names={c['unique_names']} rows={c['n_raw_rows']}"
        )

    return entity_map


def run_entity_resolution():
    log.info("=" * 60)
    log.info("ENTITY RESOLUTION START")
    log.info("=" * 60)

    con = duckdb.connect(DB_PATH)
    df = con.execute("SELECT * FROM clean_scrape").df()
    log.info(f"loaded {len(df):,} rows from clean_scrape")

    df["domain"] = df["website_clean"].apply(extract_domain)
    df["normalised_name"] = df["company_name"].apply(normalise_name)
    log.info(
        f"unique phones={df['phone_clean'].nunique():,}  "
        f"unique domains={df['domain'].nunique():,}  "
        f"unique names={df['company_name'].nunique():,}"
    )

    entity_id = assign_entities(df)
    entity_map = build_entity_map(df, entity_id)

    log.info(f"raw rows in: {len(df):,}, entities out: {len(entity_map):,}, "
             f"dedup ratio: {len(df) / len(entity_map):.1f}x")

    top = entity_map.nlargest(10, "n_raw_rows")
    log.info("top 10 entities by raw row count:")
    for _, row in top.iterrows():
        log.info(f"  [{row['entity_id']}] {row['canonical_name']} | {row['canonical_phone']} "
                  f"| {row['categories']} | {row['n_raw_rows']} rows")

    output_cols = ["entity_id", "canonical_name", "canonical_phone", "categories", "n_raw_rows"]
    entity_map[output_cols].to_csv(OUTPUT_CSV, index=False)
    log.info(f"wrote {OUTPUT_CSV} ({len(entity_map):,} entities)")

    con.execute("DROP TABLE IF EXISTS entity_map")
    con.execute("CREATE TABLE entity_map AS SELECT * FROM entity_map")
    con.close()

    log.info("=" * 60)
    log.info("ENTITY RESOLUTION COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    run_entity_resolution()
