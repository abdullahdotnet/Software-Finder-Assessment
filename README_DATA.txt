Daily exports from our vendor web-scrape process.
Range: 2026-06-01 to 2026-07-12 (one CSV per day, file name = scrape date).
Categories covered: ERP, Medical, HR, MSP Platform, LMS, Legal.

Documented schema (as specified at project start, 2026-06-01):
  scrape_date, category, company_name, phone, email, website,
  employee_count, city, country, scraped_at

vendor_reference.csv is a partial list of manually verified vendors
(name, website, category, employee band). It is incomplete but trustworthy.

Treat data quality as unknown.
