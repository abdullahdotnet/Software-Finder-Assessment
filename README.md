# Software Finder — Data Engineering Assessment

Ingests 42 daily vendor-scrape CSVs into DuckDB, cleans them, deduplicates to unique
companies, builds a star schema, and runs the 5 required queries.

## Setup

Requires Python 3.10+.

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -c "import duckdb, pandas; print(duckdb.__version__)"
```

Before running anything, make sure these three vendor-supplied inputs are sitting in
the project root (they're gitignored, so they don't come with the clone):

- `daily/` — the 42 `scrape_YYYY-MM-DD.csv` files
- `vendor_reference.csv`
- `README_DATA.txt`

## Running the full pipeline

Run these in order — each stage reads what the previous one wrote to `scrape.duckdb`:

```
python ingest.py               # 42 CSVs -> raw_scrape table
python clean.py                # raw_scrape -> clean_scrape (standardised phone/email/category)
python entity_resolution.py    # clean_scrape -> entity_map table + entity_map.csv
python model.py                # star schema (dim_date, dim_category, dim_entity, dim_location, fact_scrape)
python queries.py              # runs q1-q5, writes each as a CSV in the project root
```

Takes well under a minute end to end on the full dataset. Each stage also writes a log
to `logs/` (`ingest.log`, `clean.log`, `entity_resolution.log`, `model.log`,
`queries.log`) with row counts and every data-quality issue it hit along the way.

## Running the tests

```
python -m pytest unit_tests.py -v
```

Covers the 3 transforms most likely to break something downstream if wrong:
`clean_phone` (graded directly against the brief's spec), `clean_category` (wrong
mapping breaks every query that groups by category), and `extract_domain` (drives
entity resolution's domain-matching pass).


`explore.ipynb`, `ddl_test.ipynb`, and `queries_test.ipynb` are scratch notebooks from
building this not part of the pipeline itself.
