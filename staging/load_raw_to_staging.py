import os
import re
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text



# PATHS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"

LOG_DIR.mkdir(exist_ok=True)

CANDIDATE_INPUTS = [
    BRONZE_DIR / "raw_listings.csv",
    DATA_DIR / "avito_rawdata.csv",
]

LOG_FILE = LOG_DIR / "staging_loader.log"



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

def find_input_file() -> Path:
    for path in CANDIDATE_INPUTS:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No input CSV found. Expected one of:\n" + "\n".join(str(p) for p in CANDIDATE_INPUTS)
    )


def clean_value(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value in {"", "nan", "None"}:
        return None
    return value


def split_location(location_text):
    if not location_text:
        return None, None

    location_text = re.sub(
        r"^Appartements?\s+dans\s+",
        "",
        str(location_text),
        flags=re.IGNORECASE,
    ).strip()

    parts = [p.strip() for p in location_text.split(",") if p.strip()]

    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], None
    return None, None


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Case 1: working scraper columns
    if {"title", "price", "location", "surface", "rooms", "baths", "link"}.issubset(df.columns):
        out = pd.DataFrame()
        out["title"] = df["title"].apply(clean_value)
        out["price_raw"] = df["price"].apply(clean_value)
        out["location_raw"] = df["location"].apply(clean_value)
        out["surface_raw"] = df["surface"].apply(clean_value)
        out["rooms_raw"] = df["rooms"].apply(clean_value)
        out["baths_raw"] = df["baths"].apply(clean_value)
        out["listing_url"] = df["link"].apply(clean_value)

        split_vals = out["location_raw"].apply(split_location)
        out["city_raw"] = split_vals.apply(lambda x: x[0] if x else None)
        out["district_raw"] = split_vals.apply(lambda x: x[1] if x else None)

        out["floor_raw"] = None
        out["construction_year_raw"] = None

    # Case 2: French columns
    elif {"Titre de l’annonce", "Prix", "Ville", "Quartier", "Lien vers l’annonce"}.issubset(df.columns):
        out = pd.DataFrame()
        out["title"] = df["Titre de l’annonce"].apply(clean_value)
        out["price_raw"] = df["Prix"].apply(clean_value)
        out["city_raw"] = df["Ville"].apply(clean_value)
        out["district_raw"] = df["Quartier"].apply(clean_value)
        out["location_raw"] = (
            out["city_raw"].fillna("") + ", " + out["district_raw"].fillna("")
        ).str.strip(", ").replace("", None)

        out["surface_raw"] = (
            df["Surface (m²)"].apply(clean_value)
            if "Surface (m²)" in df.columns
            else None
        )
        out["rooms_raw"] = (
            df["Nombre de chambres"].apply(clean_value)
            if "Nombre de chambres" in df.columns
            else None
        )
        out["baths_raw"] = (
            df["Nombre de salles de bain"].apply(clean_value)
            if "Nombre de salles de bain" in df.columns
            else None
        )
        out["floor_raw"] = (
            df["Étage"].apply(clean_value)
            if "Étage" in df.columns
            else None
        )
        out["construction_year_raw"] = (
            df["Année de construction"].apply(clean_value)
            if "Année de construction" in df.columns
            else None
        )
        out["listing_url"] = df["Lien vers l’annonce"].apply(clean_value)

    else:
        raise ValueError("Unsupported CSV columns:\n" + ", ".join(df.columns))

    out["source_site"] = "avito.ma"
    out["page_number"] = None
    out["status_scrape"] = "success"

    out = out.drop_duplicates(subset=["listing_url"], keep="first")
    out = out[out["listing_url"].notna()].copy()

    return out



# LOAD

def load_to_staging(df: pd.DataFrame):
    engine = get_engine()

    insert_sql = text(
        """
        INSERT INTO staging.raw_listings (
            title,
            price_raw,
            city_raw,
            district_raw,
            location_raw,
            surface_raw,
            rooms_raw,
            baths_raw,
            floor_raw,
            construction_year_raw,
            listing_url,
            source_site,
            page_number,
            status_scrape
        )
        VALUES (
            :title,
            :price_raw,
            :city_raw,
            :district_raw,
            :location_raw,
            :surface_raw,
            :rooms_raw,
            :baths_raw,
            :floor_raw,
            :construction_year_raw,
            :listing_url,
            :source_site,
            :page_number,
            :status_scrape
        )
        ON CONFLICT (listing_url) DO NOTHING;
        """
    )

    records = df.to_dict(orient="records")

    with engine.begin() as conn:
        for record in records:
            conn.execute(insert_sql, record)

    logger.info("Inserted %s rows into staging.raw_listings", len(records))
    print(f"Inserted {len(records)} rows into staging.raw_listings")



# MAIN

def main():
    input_file = find_input_file()
    logger.info("Using input file: %s", input_file)

    df = pd.read_csv(input_file, encoding="utf-8-sig")
    logger.info("CSV loaded: %s rows", len(df))

    df = normalize_dataframe(df)
    df = df.where(pd.notna(df), None)
    logger.info("Normalized rows: %s", len(df))

    load_to_staging(df)


if __name__ == "__main__":
    main()