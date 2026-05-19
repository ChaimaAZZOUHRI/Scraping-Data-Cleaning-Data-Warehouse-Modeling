# Avito Real Estate Data Pipeline

An end-to-end data pipeline designed to transform raw real-estate advertisements scraped from **Avito.ma** into structured datasets ready for **business intelligence** and **machine learning**.

---

## General pipeline architecture

This project is based on an end-to-end data pipeline that transforms raw real-estate advertisements into structured and enriched datasets for analytical and predictive use.

The workflow follows this sequence:

**Scraping → Staging → Clean → Feature engineering → Warehouse**

- In the **scraping** phase, property advertisement data is extracted from the source website.
- In the **staging** phase, the raw data is stored in a temporary landing zone inside the database.
- In the **cleaning** phase, duplicates, inconsistent formats, and invalid values are handled.
- In the **feature engineering** phase, new derived variables are created to enrich the dataset.
- In the **warehouse** phase, the processed data is loaded into two different structures:
  - a schema optimized for business intelligence (**BI schema**)
  - a schema optimized for machine learning (**ML schema**)

---

## Difference between Bronze, Silver, and Gold

The project follows a modern layered data architecture.

### Bronze

The **Bronze** layer contains the raw scraped data, with minimal or no transformation.  
In this project, it corresponds to the original advertisement dataset produced by the scraper.

Its purpose is to preserve the source data in its initial form.

### Silver

The **Silver** layer contains cleaned and standardized data.  
At this stage, the dataset becomes analytically usable after:

- duplicate removal
- harmonization of city and district names
- conversion of textual fields into numeric values
- handling of invalid or unrealistic values

### Gold

The **Gold** layer contains enriched and ready-to-use datasets.  
In this project, it is divided into two outputs:

- a **BI-ready** dataset for reporting and dashboarding
- an **ML-ready** dataset for machine learning preparation

### Summary

- **Bronze** = raw data
- **Silver** = cleaned data
- **Gold** = enriched, ready-to-use data

---

## Cleaning operations

The cleaning phase was implemented to improve data quality and ensure analytical consistency.

The main operations were:

- removing unnecessary spaces from text values
- converting empty or invalid strings into missing values
- removing duplicate records using the advertisement **URL** as a near-unique identifier
- standardizing city and district names
- extracting numeric values from text-based fields such as:
  - price
  - surface area
  - number of rooms
  - number of bathrooms
- normalizing special floor values such as:
  - **Ground floor (Rez-de-chaussée)** = `0`
  - **Basement (Sous-sol)** = `-1`
  - **Mezzanine** = `0.5`
- applying simple business rules to nullify unrealistic values, such as:
  - extremely low or extremely high prices
  - unrealistic surface areas
  - impossible room or bathroom counts
  - invalid construction years

At the end of the cleaning stage, a structured dataset containing the main analytical variables was produced.

---

## Feature engineering

After cleaning, a feature engineering phase was applied in order to generate additional variables that increase the analytical value of the data.

The main derived features include:

- `price_per_m2`: property price per square meter
- `property_age`: estimated age of the property based on construction year
- `floor_group`: floor category such as ground floor, low floor, mid floor, or high floor
- `price_segment`: price category
- `surface_segment`: size category based on surface area
- `has_price`
- `has_surface`
- `has_rooms`
- `has_bathrooms`
- `has_floor`
- `has_construction_year`
- `is_ground_floor`
- `is_basement`
- `city_district`: combined location variable joining city and district

This phase transformed the dataset from a cleaned table into a richer analytical asset suitable for reporting and predictive use.

---

## BI schema and ML schema

### BI schema

The **BI schema** was designed for business intelligence and reporting purposes.

It consists of:

- a fact table: `fact_listings`
- a time dimension: `dim_time`
- a location dimension: `dim_location`
- a property dimension: `dim_property`

This dimensional structure facilitates analytical queries, aggregations, and dashboard integration in tools such as Power BI.

### ML schema

The **ML schema** was designed as a **One Big Table (OBT)** containing all relevant features in a single flat dataset.

This structure is more convenient for machine learning workflows because it reduces the need for joins during model preparation.

### Summary

- **BI schema** = reporting and business analysis
- **ML schema** = predictive modeling preparation

---

## Data validation

A final validation phase was conducted to ensure the reliability and consistency of the warehouse.

This phase included several checks:

- row counts were verified across the major layers:
  - staging
  - clean
  - BI warehouse
  - ML warehouse
- sample records were inspected to confirm that the main fields were correctly populated
- referential integrity was tested inside the BI schema by checking that all rows in the fact table were properly linked to the dimension tables

Returning `0` in orphan-record validation queries confirmed that the warehouse relationships were valid.

This means the following points were verified:

- data warehouse consistency
- quality of loaded data
- integrity of relationships
- completeness of BI and ML datasets

---

## Docker Compose

The project was also prepared using **Docker Compose** in order to support reproducible and portable execution.

The `docker-compose.yml` file defines two main services:

### PostgreSQL service

This service provides the database in an isolated container, with:

- persistent data storage through a Docker volume
- a health check to ensure the database is ready before the pipeline starts

### Pipeline service

This service provides a Python runtime environment in a separate container.

It:

- installs the project dependencies
- executes the main pipeline script

Docker Compose makes it possible to run the full project with a single command while ensuring a consistent execution environment across machines.

This is especially useful for:

- reproducibility
- presentation
- deployment readiness

---

## Project structure

```text
avito-real-estate-data-pipeline/
├── .venv/
├── clean/
│   ├── cleaning.py
│   └── feature_engineering.py
├── data/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│       ├── bi/
│       └── ml/
├── docs/
├── extract/
│   └── scraper_avito.py
├── logs/
├── pipeline/
│   └── run_pipeline.py
├── staging/
│   ├── create_staging_tables.sql
│   └── load_raw_to_staging.py
├── warehouse/
│   ├── create_bi_schema.sql
│   ├── create_ml_schema.sql
│   └── load_warehouse.py
├── .env
├── .gitignore
├── docker-compose.yml
├── README.md
└── requirements.txt
