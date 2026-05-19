CREATE SCHEMA IF NOT EXISTS ml_schema;

DROP TABLE IF EXISTS ml_schema.ml_ready_listings;

CREATE TABLE ml_schema.ml_ready_listings (
    ml_id SERIAL PRIMARY KEY,
    listing_url TEXT UNIQUE,

    price NUMERIC,
    city VARCHAR(255),
    district VARCHAR(255),
    surface_m2 NUMERIC,
    rooms NUMERIC,
    bathrooms NUMERIC,
    floor NUMERIC,
    construction_year INT,

    price_per_m2 NUMERIC,
    property_age NUMERIC,

    has_price INT,
    has_surface INT,
    has_rooms INT,
    has_bathrooms INT,
    has_floor INT,
    has_construction_year INT,

    is_ground_floor INT,
    is_basement INT
);

CREATE INDEX idx_ml_ready_price
ON ml_schema.ml_ready_listings(price);

CREATE INDEX idx_ml_ready_city
ON ml_schema.ml_ready_listings(city);

CREATE INDEX idx_ml_ready_district
ON ml_schema.ml_ready_listings(district);

CREATE INDEX idx_ml_ready_surface
ON ml_schema.ml_ready_listings(surface_m2);


SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'ml_schema';

SELECT * 
FROM ml_schema.ml_ready_listings
LIMIT 5;


SELECT COUNT(*) FROM bi_schema.fact_listings;
SELECT COUNT(*) FROM ml_schema.ml_ready_listings;


SELECT * FROM bi_schema.fact_listings LIMIT 5;
SELECT * FROM ml_schema.ml_ready_listings LIMIT 5;


SELECT COUNT(*) FROM clean.clean_listings;
SELECT * FROM clean.clean_listings LIMIT 5;



SELECT COUNT(*) FROM bi_schema.fact_listings;
SELECT COUNT(*) FROM ml_schema.ml_ready_listings;


SELECT COUNT(*) FROM staging.raw_listings;
SELECT COUNT(*) FROM clean.clean_listings;
SELECT COUNT(*) FROM bi_schema.fact_listings;
SELECT COUNT(*) FROM ml_schema.ml_ready_listings;



SELECT * FROM clean.clean_listings LIMIT 5;
SELECT * FROM bi_schema.fact_listings LIMIT 5;
SELECT * FROM ml_schema.ml_ready_listings LIMIT 5;



SELECT COUNT(*) 
FROM bi_schema.fact_listings f
LEFT JOIN bi_schema.dim_time t ON f.time_id = t.time_id
WHERE t.time_id IS NULL;

SELECT COUNT(*) 
FROM bi_schema.fact_listings f
LEFT JOIN bi_schema.dim_location l ON f.location_id = l.location_id
WHERE l.location_id IS NULL;

SELECT COUNT(*) 
FROM bi_schema.fact_listings f
LEFT JOIN bi_schema.dim_property p ON f.property_id = p.property_id
WHERE p.property_id IS NULL;