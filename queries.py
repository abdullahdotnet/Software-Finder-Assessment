'''
Stage 4 - runs q1-q5 and writes each
one out as a CSV.
'''

import duckdb
import pandas as pd
import logging
import sys
from pathlib import Path

DB_PATH = "scrape.duckdb"
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "queries.log"

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
queries = {

    "q1_daily_unique_phones.csv": """

        select date_id as scrape_date, dc.category_name as category,
               count(distinct phone_clean) as unique_phones
        from fact_scrape fs
        join dim_category dc on fs.category_id = dc.category_id
        group by date_id, dc.category_name
        order by date_id, dc.category_name;

    """,

    "q2_new_vs_returning.csv": """

        with first_appearance as (
            select entity_id, min(date_id) as first_seen_date
            from fact_scrape
            where entity_id != -1
            group by entity_id
        ),

        daily_entities as (
            select distinct date_id, entity_id
            from fact_scrape
            where entity_id != -1
        )

        select
            de.date_id as scrape_date,
            count(case when de.date_id = fa.first_seen_date then 1 end) as new_entities,
            count(case when de.date_id > fa.first_seen_date then 1 end) as returning_entities
        from daily_entities de
        join first_appearance fa on de.entity_id = fa.entity_id
        group by de.date_id
        order by de.date_id;

    """,

    "q3_cross_category_entities.csv": """

        select canonical_name as entity_name, all_categories as categories, first_seen
        from dim_entity
        where all_categories like '%|%'
        order by canonical_name;

    """,

    "q4_top_domains.csv": """

        select
            regexp_replace(
                regexp_replace(lower(website_clean), '^https?://', ''),
                '^www\\.',
                ''
            ) as domain,
            count(*) as row_count
        from fact_scrape
        where website_clean is not null
        group by domain
        order by row_count desc
        limit 10;

    """,

    "q5_weekly_change.csv": """

        with weekly as (
            select
                dd.week_start,
                dc.category_name as category,
                count(distinct fs.phone_clean) as unique_phones
            from fact_scrape fs
            join dim_date dd on fs.date_id = dd.date_id
            join dim_category dc on fs.category_id = dc.category_id
            group by dd.week_start, dc.category_name
        ),

        with_lag as (
            select
                week_start,
                category,
                unique_phones,
                lag(unique_phones) over (
                    partition by category
                    order by week_start
                ) as prev_week_phones
            from weekly
        )

        select
            week_start,
            category,
            unique_phones,
            round(
                (unique_phones - prev_week_phones) * 100.0
                / nullif(prev_week_phones, 0),
                2
            ) as pct_change
        from with_lag
        order by week_start, category;

    """,
}



def run_model():
    log.info("=" * 60)
    log.info("QUERIES START")
    log.info("=" * 60)

    con = duckdb.connect(DB_PATH)

  

    for filename, sql in queries.items():
        df = con.execute(sql).df()
        df.to_csv(filename, index=False)
        log.info(f"{filename}: {len(df):,} rows")
        log.info(f"{df.head(3).to_string()}")

    con.close()
    log.info("===================")
    log.info("QUERIES COMPLETE")
    log.info("===================")


if __name__ == "__main__":
    run_model()
