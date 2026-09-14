Ingestion

Read everything as string dtype Pandas guesses column types if you let it. It guesses wrong on phone numbers, drops leading zeros, and sometimes misparses dates. Reading everything as string and converting later is just safer.

Kept source_url even though it wasn't in the schema From June 24 onwards the files had an extra source_url column not mentioned in README_DATA.txt. I kept it rather than dropping it. Didn't know if it would matter later and silently dropping data felt wrong. It ended up being useful for confirming exactly when the schema changed.

Added _source_file and _file_date to every row Not in the original schema but helpful for debugging. When a bad row shows up downstream you want to know which file it came from without re-reading 42 CSVs.


