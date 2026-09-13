# DQ_REPORT.md

42 files, 2026-06-01 to 2026-07-12, 245,169 raw rows.

| # | Issue | First seen | Scope | How detected | Pipeline handling | Downstream risk |
|---|---|---|---|---|---|---|
| 1 | Category labels inconsistent — `Legal`/`legal`/`LEGAL `/`Lgl` all mean the same thing (note the LEGAL variant has a trailing space) | 2026-06-20 | 8,985 rows, 23 files (06-20 → 07-12) | `GROUP BY category` returned 9 values instead of 6 | strip whitespace, map all variants to `Legal` in clean.py | queries filtering `category = 'Legal'` on raw data miss 27% of Legal rows |
| 2 | A header row got ingested as a data row | n/a — single row, can't trace to one source file | 1 row | `category`, `company_name`, `scrape_date` all equal their own column name on that row | drop any row where those 3 columns match their own name | small on its own, but would throw off entity resolution and every category count |
| 3 | Phone numbers arrive in 8+ formats | 2026-06-01 | all 245,169 rows | sampled distinct phone strings by hand | strip extensions, strip non-digits, drop a leading 1 or 0, require 10 digits left, flag (not drop) anything short | same company's number in two formats double-counts and breaks q1/q5 |
| 4 | `source_url` column shows up 3.5 weeks into the dataset with no warning | 2026-06-24 | 19 of 42 files have it; the other 121,717 rows don't | ingestion loader flagged it as an unexpected column | kept it, treat pre-06-24 nulls as expected rather than a defect | fine today, but breaks if it's ever used for dedup/joins — half the rows have nothing to match |
| 5 | 06-17 has ~1,100 fewer rows than the days around it | 2026-06-17 | 1 file — 4,488 rows vs ~5,500-5,900 on 06-16/06-18 | eyeballing the daily row-count breakdown | loaded as-is — not padding it out with fabricated rows | week-over-week trend around that date will look artificially low; worth asking the data owner about it |
| 6 | Went looking for the classic "nan"/"none"/"null" string-instead-of-empty problem | — | 0 rows | queried every column for literal `nan`/`none`/`null`/`n/a` — none exist in this dataset | left the defensive check in clean.py anyway, costs nothing | none right now — would matter silently if a future export starts doing this |
| 7 | 2,426 malformed emails | 2026-06-01 | 2,426 rows (~1%) | anything missing `@` or `.` gets flagged | marked invalid, not dropped | low — email isn't used in q1-q5, but still worth knowing about |

A couple of things that came out of digging into #3 and #6 that are worth calling out on their own:

Once the extensions and punctuation are stripped off, every phone number in this dataset lands on either 10 or 11 digits — nothing shorter, nothing longer. Of the 11-digit ones, most (85,744) start with a `1`, which is just the US country code. But a chunk of them (7,371) start with `0` instead — same idea, just a different leading digit to drop. Both cases resolve cleanly to 10 digits, which is why the phone cleaning step comes out at 100% valid. That felt too clean to trust at first, so I checked the actual digit-length distribution rather than take the 100% number at face value.

For #6, I'd actually expected to find literal `"nan"` strings somewhere, since `safe_read_csv` reads everything as `dtype=str` and pandas has a habit of writing `"nan"` into string-typed empty cells. Checked all 11 columns directly against the raw table and came up empty — genuinely clean on this front. Kept the check in the code anyway since it's a one-line safeguard against a real failure mode, just not one that showed up this time.
