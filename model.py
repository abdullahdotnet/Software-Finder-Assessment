"""
Stage 4 - star schema + the five required queries.

Builds dim_date / dim_category / dim_entity / dim_location / fact_scrape in
scrape.duckdb from clean_scrape + entity_map
"""

import duckdb
import pandas as pd
import logging
import sys
from pathlib import Path

DB_PATH = "scrape.duckdb"
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "model.log"

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


DDL = """
-- dimenstions
create or replace table dim_date as
select distinct scrape_date as date_id,
cast(scrape_date as date) as full_date,
year(cast(scrape_date as date)) as year,
month(cast(scrape_date as date)) as month,
day(cast(scrape_date as date)) as day,
dayofweek(cast(scrape_date as date)) as day_of_week,
cast(cast(date_trunc('week', cast(scrape_date as date)) as date) as varchar) as week_start
from clean_scrape
where scrape_date is not null
order by date_id;

create or replace table dim_category as
select row_number() over (order by category) as category_id, category as category_name
from (select distinct category from clean_scrape where category is not null and category != 'Unknown') t
order by category;

create or replace table dim_entity as
select entity_id, canonical_name, canonical_phone, categories as all_categories, n_raw_rows, first_seen
from entity_map
order by entity_id;


create or replace table dim_location as
select row_number() over (order by country, city) as location_id,
case when trim(city) in ('-', 'NaN', 'none', 'null', 'n/a', '')
    then null
    else city
end as city,
country
from (select distinct 
case when trim(city) in ('-', 'NaN', 'none', 'null', 'n/a', '')
    then null
    else city
end as city,
country from clean_scrape where country is not null) t
order by country, city;


--fact
create or replace table fact_scrape as
select row_number() over () as fact_id,
cs.scrape_date as date_id,
dc.category_id,
coalesce(em.entity_id, -1) as entity_id,
coalesce(dl.location_id, -1) as location_id,
cs.phone_clean,
cs.email_clean,
cs.website_clean,
cs.employee_count,
cs._source_file,
cs.scraped_at
from clean_scrape cs
left join dim_category dc ON cs.category = dc.category_name
left join entity_map em ON cs.phone_clean = em.canonical_phone
left join dim_location dl
on coalesce(cs.city, '__null__') = coalesce(dl.city, '__null__')
and cs.country = dl.country
where cs.scrape_date is not null;
"""





def run_model():
    log.info("=" * 60)
    log.info("MODEL + QUERIES START")
    log.info("=" * 60)

    con = duckdb.connect(DB_PATH)

    con.execute(DDL)
    for table in ["dim_date", "dim_category", "dim_entity", "dim_location", "fact_scrape"]:
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        log.info(f"  {table:<20} {count:>10,} rows")



    con.close()
    log.info("=" * 60)
    log.info("MODEL + QUERIES COMPLETE")
    log.info("=" * 60)


if __name__ == "__main__":
    run_model()
