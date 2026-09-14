# DQ_REPORT.md

42 files, 2026-06-01 to 2026-07-12, 245,169 raw rows.

---

| # | Issue | First seen | Scope | How detected | Pipeline handling | Downstream risk |
|---|---|---|---|---|---|---|
| 1 | Category labels inconsistent: `Legal`/`legal`/`LEGAL`/`Lgl` all mean the same thing. `LEGAL` also has a trailing space. | 2026-06-20 | 8,985 rows, 23 files | `GROUP BY category` returned 9 values instead of 6 | Strip whitespace, map all variants to `Legal` in clean.py | Queries on raw data miss 27% of Legal rows |
| 2 | A header row got ingested as a data row | Can't trace to one file | 1 row | `category`, `company_name`, `scrape_date` all equal their own column name | Drop any row where those 3 fields match their column name | Small on its own but throws off entity resolution and category counts |
| 3 | Phone numbers arrive in 8+ formats | 2026-06-01 | All 245,169 rows | Sampled distinct phone strings | Strip extensions first, then non-digits, drop a leading 1 or 0, require exactly 10 digits, flag anything that doesn't make it | Same number in two formats double-counts and breaks q1 and q5 |
| 4 | `source_url` appeared 3.5 weeks in with no warning | 2026-06-24 | 19 of 42 files have it, 121,717 rows don't | Ingestion flagged it as an unexpected column | Kept it, pre-06-24 nulls treated as expected | Fine today, breaks if it's ever used for dedup, half the rows have nothing to match on |
| 5 | June 17 has ~1,100 fewer rows than surrounding days | 2026-06-17 | 1 file 4,488 rows vs ~5,500-5,900 on either side | Eyeballing the daily row count breakdown | Loaded as-is, not padding with fabricated rows | Week-over-week trend around that date looks artificially low |
| 6 | Checked for "nan"/"none"/"null" strings stored instead of empty, none found | — | 0 rows | Queried every column directly against the raw table | Left the defensive check in clean.py anyway, costs nothing | None right now, would matter silently if a future export starts doing this |
| 7 | 2,426 malformed emails | 2026-06-01 | 2,426 rows (~1%) | Anything missing `@` or `.` gets flagged | Marked invalid, not dropped | Low - email isn't used in q1-q5 |
| 8 | `-` used as a city placeholder instead of leaving it empty | 2026-06-01 | Multiple rows | Spotted in dim\_location output | Added `-` to the null string list in clean.py | Would be counted as a real city without the fix |

---

Few important things from digging into issues 3 and 6.

On phones, once extensions and punctuation are stripped, every number
lands on either 10 or 11 digits, nothing else. Of the 11-digit ones,
85,744 start with 1 (US country code) and 7,371 start with 0. Both
cases clean down to 10 digits, which is why the cleaning step comes
out at 100% valid. That felt too clean to trust at first so I checked
the actual digit-length distribution rather than just take the number
at face value.

On the nan strings, I expected to find some. The ingestion script
reads everything as dtype=str and pandas has a habit of writing "nan"
into empty string cells. Checked all 11 columns against the raw table
and came up empty. Kept the check in the code anyway since it's a
one-liner and protects against a real failure mode, just not one that
showed up this time.