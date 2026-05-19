# Architecture note

## Pipeline flow
Scraping → Staging → Clean → Feature engineering → Warehouse

## Layers
- Bronze: raw scraped data
- Silver: cleaned data
- Gold: enriched BI-ready and ML-ready datasets

## Warehouse
- BI schema:
  - fact_listings
  - dim_time
  - dim_location
  - dim_property
- ML schema:
  - ml_ready_listings

## Automation
The pipeline is automated with Docker Compose and run_pipeline.py.

## Validation
Final validation checks:
- row counts
- referential integrity
- completeness of BI and ML datasets