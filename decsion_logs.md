## Ingestion

* Read all columns as strings to avoid Pandas guessing types incorrectly, especially for phones and dates.
* Kept source\_url even though it wasn't in the original schema. It appeared from June 24 onwards and helped identify the schema change.
* Added \_source\_file and \_file\_date for easier debugging and tracing records back to the source file.

## Cleaning

* Used a lookup dictionary for category variants instead of fuzzy matching. Unknown values are flagged rather than dropped.
* Removed phone extensions before stripping non-digits so extensions don't become part of the phone number.
* Added phone\_clean\_flag instead of dropping invalid phones. All 245,168 phones cleaned successfully.
* Added `-` to the null values after finding it in the city data.

## Entity Resolution

* Used phone first, domain second, and name last since phone/domain are stronger matches.
* Used `pd.factorize` instead of row-by-row loops for faster processing.
* Set the name similarity threshold to `0.90`. Lower values caused some incorrect matches, while higher values missed obvious name variations.
* Used the most frequent name and phone as the canonical values.

## Modelling


* Used -1 for unmatched entity\_id so unknown entities are easy to identify.
* Kept model.py and queries.py separate so the queries can be rerun without rebuilding the database.
* Added scrape.duckdb to .gitignore. The database is a build artifact and can be recreated from the scripts.
