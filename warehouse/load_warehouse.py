import os
import logging
from pathlib import Path
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text



# PATHS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
GOLD_BI_FILE = PROJECT_ROOT / "data" / "gold" / "bi" / "bi_ready_listings.csv"
GOLD_ML_FILE = PROJECT_ROOT / "data" / "gold" / "ml" / "ml_ready_listings.csv"

LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "warehouse_loader.log"



# LOGGING

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)



# ENV / DB

load_dotenv(PROJECT_ROOT / ".env")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "avito_dw")


def get_engine():
    url = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    return create_engine(url)



# HELPERS

def clean_string(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value in {"", "nan", "None"}:
        return None
    return value


def prepare_bi_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    expected_cols = [
        "title",
        "price",
        "city",
        "district",
        "surface_m2",
        "rooms",
        "bathrooms",
        "floor",
        "construction_year",
        "listing_url",
        "price_per_m2",
        "property_age",
        "floor_group",
        "price_segment",
        "surface_segment",
        "city_district",
        "has_price",
        "has_surface",
        "has_rooms",
        "has_bathrooms",
        "has_floor",
        "has_construction_year",
        "is_ground_floor",
        "is_basement",
    ]

    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing BI columns: {missing}")

    if "scrape_date" not in df.columns:
        df["scrape_date"] = pd.to_datetime(date.today())

    text_cols = [
        "title",
        "city",
        "district",
        "listing_url",
        "floor_group",
        "price_segment",
        "surface_segment",
        "city_district",
    ]
    for col in text_cols:
        df[col] = df[col].apply(clean_string)

    numeric_cols = [
        "price",
        "surface_m2",
        "rooms",
        "bathrooms",
        "floor",
        "construction_year",
        "price_per_m2",
        "property_age",
        "has_price",
        "has_surface",
        "has_rooms",
        "has_bathrooms",
        "has_floor",
        "has_construction_year",
        "is_ground_floor",
        "is_basement",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["scrape_date"] = pd.to_datetime(df["scrape_date"], errors="coerce").dt.date
    df["scrape_date"] = df["scrape_date"].fillna(date.today())

    df = df.drop_duplicates(subset=["listing_url"], keep="first")
    df = df[df["listing_url"].notna()].copy()

    return df


def prepare_ml_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "listing_url" not in df.columns:
        df["listing_url"] = [f"ml_row_{i}" for i in range(len(df))]

    expected_cols = [
        "listing_url",
        "price",
        "city",
        "district",
        "surface_m2",
        "rooms",
        "bathrooms",
        "floor",
        "construction_year",
        "price_per_m2",
        "property_age",
        "has_price",
        "has_surface",
        "has_rooms",
        "has_bathrooms",
        "has_floor",
        "has_construction_year",
        "is_ground_floor",
        "is_basement",
    ]

    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing ML columns: {missing}")

    text_cols = ["listing_url", "city", "district"]
    for col in text_cols:
        df[col] = df[col].apply(clean_string)

    numeric_cols = [
        "price",
        "surface_m2",
        "rooms",
        "bathrooms",
        "floor",
        "construction_year",
        "price_per_m2",
        "property_age",
        "has_price",
        "has_surface",
        "has_rooms",
        "has_bathrooms",
        "has_floor",
        "has_construction_year",
        "is_ground_floor",
        "is_basement",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[expected_cols].drop_duplicates(subset=["listing_url"], keep="first")
    df = df[df["listing_url"].notna()].copy()

    return df



# LOAD BI SCHEMA

def load_bi_schema(engine, bi_df: pd.DataFrame):
    with engine.begin() as conn:
        conn.execute(text("""
            TRUNCATE TABLE
                bi_schema.fact_listings,
                bi_schema.dim_time,
                bi_schema.dim_location,
                bi_schema.dim_property
            RESTART IDENTITY CASCADE;
        """))

    # dim_time
    dim_time = bi_df[["scrape_date"]].drop_duplicates().copy()
    dim_time["year"] = pd.to_datetime(dim_time["scrape_date"]).dt.year
    dim_time["quarter"] = pd.to_datetime(dim_time["scrape_date"]).dt.quarter
    dim_time["month"] = pd.to_datetime(dim_time["scrape_date"]).dt.month
    dim_time["day"] = pd.to_datetime(dim_time["scrape_date"]).dt.day

    dim_time.to_sql(
        "dim_time",
        engine,
        schema="bi_schema",
        if_exists="append",
        index=False,
        method="multi",
    )

    # dim_location
    dim_location = bi_df[["city", "district", "city_district"]].drop_duplicates().copy()
    dim_location.to_sql(
        "dim_location",
        engine,
        schema="bi_schema",
        if_exists="append",
        index=False,
        method="multi",
    )

    # dim_property
    property_cols = [
        "title",
        "surface_m2",
        "rooms",
        "bathrooms",
        "floor",
        "construction_year",
        "property_age",
        "floor_group",
        "surface_segment",
        "is_ground_floor",
        "is_basement",
    ]

    dim_property = bi_df[property_cols].drop_duplicates().copy()
    dim_property.to_sql(
        "dim_property",
        engine,
        schema="bi_schema",
        if_exists="append",
        index=False,
        method="multi",
    )

    # read dimensions
    dim_time_db = pd.read_sql("SELECT * FROM bi_schema.dim_time", engine)
    dim_location_db = pd.read_sql("SELECT * FROM bi_schema.dim_location", engine)
    dim_property_db = pd.read_sql("SELECT * FROM bi_schema.dim_property", engine)

    dim_time_db["scrape_date"] = pd.to_datetime(dim_time_db["scrape_date"]).dt.date

    # build fact
    fact_df = bi_df.merge(
        dim_time_db[["time_id", "scrape_date"]],
        on="scrape_date",
        how="left",
    ).merge(
        dim_location_db[["location_id", "city", "district"]],
        on=["city", "district"],
        how="left",
    ).merge(
        dim_property_db[
            [
                "property_id",
                "title",
                "surface_m2",
                "rooms",
                "bathrooms",
                "floor",
                "construction_year",
                "property_age",
                "floor_group",
                "surface_segment",
                "is_ground_floor",
                "is_basement",
            ]
        ],
        on=[
            "title",
            "surface_m2",
            "rooms",
            "bathrooms",
            "floor",
            "construction_year",
            "property_age",
            "floor_group",
            "surface_segment",
            "is_ground_floor",
            "is_basement",
        ],
        how="left",
    )

    fact_out = fact_df[
        [
            "listing_url",
            "time_id",
            "location_id",
            "property_id",
            "price",
            "price_per_m2",
            "price_segment",
            "has_price",
            "has_surface",
            "has_rooms",
            "has_bathrooms",
            "has_floor",
            "has_construction_year",
        ]
    ].copy()

    fact_out.to_sql(
        "fact_listings",
        engine,
        schema="bi_schema",
        if_exists="append",
        index=False,
        method="multi",
    )

    print(f"Loaded BI schema: {len(fact_out)} fact rows")



# LOAD ML SCHEMA

def load_ml_schema(engine, ml_df: pd.DataFrame):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE ml_schema.ml_ready_listings RESTART IDENTITY CASCADE;"))

    ml_df.to_sql(
        "ml_ready_listings",
        engine,
        schema="ml_schema",
        if_exists="append",
        index=False,
        method="multi",
    )

    print(f"Loaded ML schema: {len(ml_df)} rows")



# MAIN

def main():
    if not GOLD_BI_FILE.exists():
        raise FileNotFoundError(f"BI file not found: {GOLD_BI_FILE}")

    if not GOLD_ML_FILE.exists():
        raise FileNotFoundError(f"ML file not found: {GOLD_ML_FILE}")

    bi_df = pd.read_csv(GOLD_BI_FILE, encoding="utf-8-sig")
    ml_df = pd.read_csv(GOLD_ML_FILE, encoding="utf-8-sig")

    bi_df = prepare_bi_dataframe(bi_df)
    ml_df = prepare_ml_dataframe(ml_df)

    engine = get_engine()

    load_bi_schema(engine, bi_df)
    load_ml_schema(engine, ml_df)

    print("Warehouse loading finished successfully.")


if __name__ == "__main__":
    main()