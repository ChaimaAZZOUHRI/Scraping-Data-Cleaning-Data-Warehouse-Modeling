CREATE SCHEMA IF NOT EXISTS bi_schema;

DROP TABLE IF EXISTS bi_schema.fact_listings;
DROP TABLE IF EXISTS bi_schema.dim_time;
DROP TABLE IF EXISTS bi_schema.dim_location;
DROP TABLE IF EXISTS bi_schema.dim_property;

CREATE TABLE bi_schema.dim_time (
    time_id SERIAL PRIMARY KEY,
    scrape_date DATE UNIQUE,
    year INT,
    quarter INT,
    month INT,
    day INT
);

CREATE TABLE bi_schema.dim_location (
    location_id SERIAL PRIMARY KEY,
    city VARCHAR(255),
    district VARCHAR(255),
    city_district VARCHAR(500),
    UNIQUE (city, district)
);

CREATE TABLE bi_schema.dim_property (
    property_id SERIAL PRIMARY KEY,
    title TEXT,
    surface_m2 NUMERIC,
    rooms NUMERIC,
    bathrooms NUMERIC,
    floor NUMERIC,
    construction_year INT,
    property_age NUMERIC,
    floor_group VARCHAR(100),
    surface_segment VARCHAR(100),
    is_ground_floor INT,
    is_basement INT,
    UNIQUE (
        title,
        surface_m2,
        rooms,
        bathrooms,
        floor,
        construction_year
    )
);

CREATE TABLE bi_schema.fact_listings (
    fact_id SERIAL PRIMARY KEY,
    listing_url TEXT UNIQUE,
    time_id INT REFERENCES bi_schema.dim_time(time_id),
    location_id INT REFERENCES bi_schema.dim_location(location_id),
    property_id INT REFERENCES bi_schema.dim_property(property_id),

    price NUMERIC,
    price_per_m2 NUMERIC,
    price_segment VARCHAR(100),

    has_price INT,
    has_surface INT,
    has_rooms INT,
    has_bathrooms INT,
    has_floor INT,
    has_construction_year INT
);

CREATE INDEX idx_fact_listings_time_id
ON bi_schema.fact_listings(time_id);

CREATE INDEX idx_fact_listings_location_id
ON bi_schema.fact_listings(location_id);

CREATE INDEX idx_fact_listings_property_id
ON bi_schema.fact_listings(property_id);

CREATE INDEX idx_fact_listings_price
ON bi_schema.fact_listings(price);

CREATE INDEX idx_dim_location_city
ON bi_schema.dim_location(city);

CREATE INDEX idx_dim_location_district
ON bi_schema.dim_location(district);

