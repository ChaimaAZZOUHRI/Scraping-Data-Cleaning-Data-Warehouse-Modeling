import logging
from datetime import datetime
from pathlib import Path

import pandas as pd



# PATHS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
SILVER_DIR = PROJECT_ROOT / "data" / "silver"
GOLD_BI_DIR = PROJECT_ROOT / "data" / "gold" / "bi"
GOLD_ML_DIR = PROJECT_ROOT / "data" / "gold" / "ml"

LOG_DIR.mkdir(exist_ok=True)
GOLD_BI_DIR.mkdir(parents=True, exist_ok=True)
GOLD_ML_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILE = SILVER_DIR / "clean_listings.csv"
BI_OUTPUT_FILE = GOLD_BI_DIR / "bi_ready_listings.csv"
ML_OUTPUT_FILE = GOLD_ML_DIR / "ml_ready_listings.csv"
LOG_FILE = LOG_DIR / "feature_engineering.log"



# LOGGING

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)



# HELPERS

def price_per_m2(price, surface):
    if pd.isna(price) or pd.isna(surface):
        return None
    if surface <= 0:
        return None
    return round(price / surface, 2)


def property_age(construction_year):
    if pd.isna(construction_year):
        return None
    current_year = datetime.now().year
    age = current_year - construction_year
    if age < 0:
        return None
    return age


def floor_group(floor):
    if pd.isna(floor):
        return "Unknown"
    if floor < 0:
        return "Basement"
    if floor == 0:
        return "Ground floor"
    if floor <= 2:
        return "Low floor"
    if floor <= 5:
        return "Mid floor"
    return "High floor"


def price_segment(price):
    if pd.isna(price):
        return "Unknown"
    if price < 500000:
        return "Budget"
    if price < 1000000:
        return "Mid-range"
    if price < 2000000:
        return "Upper mid-range"
    return "Premium"


def surface_segment(surface):
    if pd.isna(surface):
        return "Unknown"
    if surface < 50:
        return "Small"
    if surface < 100:
        return "Medium"
    if surface < 150:
        return "Large"
    return "Very large"



# MAIN

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")
    logger.info("Loaded clean dataset: %s rows", len(df))
    print(f"Loaded clean dataset: {len(df)} rows")

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
    ]
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in clean_listings.csv: {missing_cols}")

    numeric_cols = ["price", "surface_m2", "rooms", "bathrooms", "floor", "construction_year"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

  
    # FEATURE ENGINEERING
  
    df["price_per_m2"] = df.apply(lambda row: price_per_m2(row["price"], row["surface_m2"]), axis=1)
    df["property_age"] = df["construction_year"].apply(property_age)

    df["has_price"] = df["price"].notna().astype(int)
    df["has_surface"] = df["surface_m2"].notna().astype(int)
    df["has_rooms"] = df["rooms"].notna().astype(int)
    df["has_bathrooms"] = df["bathrooms"].notna().astype(int)
    df["has_floor"] = df["floor"].notna().astype(int)
    df["has_construction_year"] = df["construction_year"].notna().astype(int)

    df["is_ground_floor"] = df["floor"].apply(lambda x: 1 if pd.notna(x) and x == 0 else 0)
    df["is_basement"] = df["floor"].apply(lambda x: 1 if pd.notna(x) and x < 0 else 0)

    df["floor_group"] = df["floor"].apply(floor_group)
    df["price_segment"] = df["price"].apply(price_segment)
    df["surface_segment"] = df["surface_m2"].apply(surface_segment)

    df["city_district"] = (
        df["city"].fillna("Unknown").astype(str) + " | " + df["district"].fillna("Unknown").astype(str)
    )

   
    # BI OUTPUT
   
    bi_df = df[
        [
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
    ].copy()

    
    # ML OUTPUT
    
    ml_df = df[
        [
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
    ].copy()

    
    # SAVE

    bi_df.to_csv(BI_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    ml_df.to_csv(ML_OUTPUT_FILE, index=False, encoding="utf-8-sig")

    logger.info("Saved BI dataset to %s", BI_OUTPUT_FILE)
    logger.info("Saved ML dataset to %s", ML_OUTPUT_FILE)

    print(f"Saved BI dataset to: {BI_OUTPUT_FILE}")
    print(f"Saved ML dataset to: {ML_OUTPUT_FILE}")
    print(f"BI rows: {len(bi_df)}")
    print(f"ML rows: {len(ml_df)}")


if __name__ == "__main__":
    main()