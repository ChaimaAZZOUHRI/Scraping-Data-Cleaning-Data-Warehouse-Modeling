CREATE SCHEMA IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.raw_listings;

CREATE TABLE staging.raw_listings (
    raw_id SERIAL PRIMARY KEY,
    scrape_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    title TEXT,
    price_raw TEXT,
    city_raw TEXT,
    district_raw TEXT,
    location_raw TEXT,
    surface_raw TEXT,
    rooms_raw TEXT,
    baths_raw TEXT,
    floor_raw TEXT,
    construction_year_raw TEXT,
    listing_url TEXT UNIQUE,

    source_site VARCHAR(100) DEFAULT 'avito.ma',
    page_number INT,
    status_scrape VARCHAR(50) DEFAULT 'success'
);