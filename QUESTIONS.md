These are the main questions I would want answered before putting the pipeline into production. Some came from the data, others from decisions I had to make with limited information.

1. What caused the June 17 row count drop?

That file had ~1,100 fewer rows than the surrounding days. I'd want to know if this was a one-off scraper issue or something that happens regularly so the 20% Airflow threshold can be calibrated properly.

2. Is a company's phone number stable enough to use as the primary identifier?

The current entity resolution relies on phone matching first. It works well here, but changes or incorrect numbers could split or merge entities over time. I would want to know how often this happens.

3. How should cross category entities be handled?

270 companies appear in multiple categories. I currently count them in each category, but this can inflate category totals. I would want to confirm whether that matches the business requirement.

4. Will source_url be used for anything?

It only appears in the last 19 files. If it is going to be used for deduplication or joins, we would need to know how it should be handled for older records.

5. How is the dataset expected to grow?

Unique phone growth dropped from around 10% in week 2 to almost zero by week 6. Is the scraper approaching saturation, or are more categories and geographies planned? This would affect infrastructure sizing.