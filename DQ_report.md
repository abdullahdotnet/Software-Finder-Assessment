# DQ_REPORT.md

Dataset: 42 CSV files (2026-06-01 to 2026-07-12)
Total rows: 245,169

---

## Issues Found

### 1 — Category labels are inconsistent

- **First seen:** 2026-06-01
- **Scope:** ~9,985 rows across all 42 files
- **How detected:** When I grouped by category I got 9 distinct values instead of 6
- **What I found:** Legal appears as `Legal`, `legal`, `LEGAL` and `Lgl` — all the same thing
- **Pipeline handling:** Map all 4 variants to `Legal` in the cleaning step
- **Downstream risk:** Any query filtering on `category = 'Legal'` would miss ~9,000 rows

---

### 2 — One file's header row got loaded as a data row

- **First seen:** Unknown (single row in combined table)
- **Scope:** 1 row
- **How detected:** Noticed `category` and `scrape_date` appearing as values when grouping
- **What I found:** A row where company_name is literally "company_name" — the header got picked up as data
- **Pipeline handling:** Filter out any row where category = 'category' in cleaning
- **Downstream risk:** Small but would break entity resolution if left in

---

### 3 — Phone numbers are in many different formats

- **First seen:** 2026-06-01
- **Scope:** All 245,169 rows need checking
- **How detected:** Looked at a sample of distinct phone values, found 8+ different formats
- **What I found:** Mix of `+1 (537) 625-5317`, `884.705.5203`, `8325162691 ext. 1`, `(611) 886-6077` etc.
- **Pipeline handling:** Strip everything down to digits only, remove leading 1 or 0, strip extensions, result must be 10 digits. Anything that doesn't make it gets flagged as invalid — not dropped
- **Downstream risk:** Without this, the same number in two formats counts as two different numbers — breaks q1 and q5 completely

---

### 4 — source_url column appeared mid-dataset without any notice

- **First seen:** 2026-06-24
- **Scope:** 19 of 42 files have it, 121,717 rows do not
- **How detected:** Ingestion script flagged it as an unexpected column, confirmed with a per-day breakdown
- **What I found:** Hard cutover on June 24 — every file before that date has zero values, every file after has it fully populated. Not mentioned in README_DATA.txt at all
- **Pipeline handling:** Keep the column, treat NULLs before June 24 as expected
- **Downstream risk:** Fine for now, but if source_url ever gets used for deduplication half the dataset has nothing

---

### 5 — June 17 has noticeably fewer rows than surrounding days

- **First seen:** 2026-06-17
- **Scope:** 1 file, roughly 1,100 rows short
- **How detected:** Rows-per-day breakdown showed 4,488 on June 17 vs ~5,500 on either side
- **What I found:** Jun 16 had 5,592 rows and Jun 18 had 5,748 — Jun 17 dropped to 4,488 with no obvious reason
- **Pipeline handling:** Not touching it — loading the file as-is and flagging here. Not going to fabricate rows
- **Downstream risk:** Week-over-week trend for that period will look off. Worth flagging to the data owner

---

### 6 — Some nulls are stored as the string "nan" instead of being empty

- **First seen:** 2026-06-01
- **Scope:** Confirmed in source_url, possibly other columns too
- **How detected:** When printing raw row values, source_url showed `nan` as text not an actual null
- **What I found:** Python wrote "nan" into the CSV instead of leaving the field empty
- **Pipeline handling:** Cleaning step will replace "nan", "none", "null", "n/a" with proper NULL across all columns
- **Downstream risk:** A `WHERE col IS NULL` check would silently skip these rows and give wrong counts