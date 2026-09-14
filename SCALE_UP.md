
The pipeline currently runs locally on 42 CSV files, 245,168 rows,
9,476 unique vendors. That's fine on a laptop. But the scraper is
still running daily and the dataset was growing at 8-10% week over
week before flattening out in week 6. Add more categories or
geographies and the volume could get unmanageable pretty quickly.

The decisions below are based on what this pipeline actually does,
one batch load per day, 6 fixed categories, a known set of queries,
not a hypothetical future state.



## My picks


- Compute engine = AWS Glue
- Serving layer = Amazon Redshift
- Orchestration = Apache Airflow
- DQ gating = dbt tests
- Lineage = OpenLineage



## Compute: AWS Glue

The pipeline runs once a day and finishes in under 2 minutes locally. Even at 10x the current volume, a serverless Glue job should still be comfortably within a reasonable batch window. Keeping a cluster running all day would not make sense for this workload.

EMR would be more useful for continuous workloads or cases requiring cluster-level tuning. Databricks would make more sense if entity resolution moved to something like embedding-based matching at much larger scale. For 9,476 entities, the current rule-based approach is easier to debug and is sufficient.

Glue also maps well to the existing three stages: ingest, clean, and resolve.



## Serving: Amazon Redshift

The current queries are mostly COUNT DISTINCT, GROUP BY, window functions, and weekly rollups. Redshift's columnar storage fits this workload well.

The existing star schema also maps directly to Redshift. dim_date has 42 rows, dim\_category has 6, and dim\_entity has 9,476, so these are small compared with fact_scrape. Distributing fact_scrape by entity\_id is a reasonable starting point since most queries group or filter by entity.

Athena would work for querying the files directly in S3, but the query set here is fixed and runs daily. Redshift gives us a more consistent serving layer for that workload.



## Orchestration: Airflow

The pipeline has a strict dependency chain:

ingest -> clean -> entity_resolution -> model -> queries


If entity resolution fails, we should not overwrite the previous day's entity map with incomplete data. Airflow handles this with task dependencies, retries, scheduling, and alerts.

Step Functions would also work, but this is a scheduled batch pipeline rather than an event-driven workflow. NiFi is mainly useful for streaming, which we don't need here.

I would also add a row-count check before ingestion. The June 17 file had roughly 1,100 fewer rows than surrounding days without an obvious reason. That should raise an alert instead of silently loading a short file.



## DQ Gating: dbt tests

We found 8 data quality issues during exploration. In production
those need to be checked automatically on every run, not just
documented.


Key tests:

- phone_clean must not be null
- category must use one of the 6 canonical values
- entity\_id must be unique in dim\_entity
- Daily row count must stay within 20% of the 7-day rolling average
- phone_clean must match ^\d{10}$

I looked into Great Expectations as well but it felt like overkill here.
We are already using dbt for the models so keeping tests there means
one less tool and everything stays version controlled together.
If the DQ requirements got more complex then it would be worth revisiting.



## Lineage: OpenLineage

With 5 pipeline stages feeding into each other, if a query output looks wrong it is not always obvious where the problem came from. Did the entity_resolution step change? Did a cleaning rule shift? OpenLineage captures that automatically across Airflow and dbt without needing custom tracking code.

The specific case that I would be worry about is the entity matching threshold. Right now name similarity threshold is set to 0.90. If someone changes that, it affects entity\_map, which affects fact\_scrape, which affects all 5 query outputs. Lineage makes that chain visible.

Unity Catalog would be the right call if the team was already on Databricks. Since we are on Glue and Redshift, OpenLineage is the better fit. It is also vendor neutral and integrates with both.


## Summary


- Compute = AWS Glue = Once-daily batch, no need for a permanent cluster
- Serving = Redshift = Columnar storage fits our aggregation-heavy queries
- Orchestration = Airflow = Linear dependencies, daily schedule, failure visibility
- DQ gating = dbt tests = Manually code the 8 known issues, already in our toolchain 
- Lineage = OpenLineage = Works across Glue + Redshift, no vendor lock-in 

Everything here is batch, not streaming. The query patterns are
fixed, not ad-hoc. The category set is small and known. The picks
reflect that nothing here is chosen to sound impressive.