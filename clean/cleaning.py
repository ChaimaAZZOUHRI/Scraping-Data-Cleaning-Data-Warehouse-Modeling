"""
cleaning.py

Purpose:
    Clean raw Avito real-estate listings from the bronze layer,
    save the cleaned data into the silver layer, and load it into PostgreSQL.

Input:
    data/bronze/raw_listings.csv

Outputs:
    data/silver/clean_listings.csv
    PostgreSQL table: clean.clean_listings

Logs:
    logs/cleaning.log
"""

import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text



# 1. PROJECT PATHS


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
LOG_DIR = PROJECT_ROOT / "logs"

BRONZE_FILE = BRONZE_DIR / "raw_listings.csv"
SILVER_FILE = SILVER_DIR / "clean_listings.csv"
LOG_FILE = LOG_DIR / "cleaning.log"

SILVER_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)



# 2. LOGGING CONFIGURATION


def setup_logger() -> logging.Logger:
    """
    Configure logging to both:
    - terminal
    - logs/cleaning.log
    """

    logger = logging.getLogger("cleaning_pipeline")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        mode="a",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()



# 3. ENVIRONMENT VARIABLES AND DATABASE CONNECTION


load_dotenv(PROJECT_ROOT / ".env")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "avito_dw")


def get_engine():
    """
    Create SQLAlchemy engine for PostgreSQL connection.
    """

    database_url = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    return create_engine(database_url)



# 4. BASIC CLEANING HELPERS


def clean_string(value):
    """
    Clean text values:
    - remove spaces
    - convert empty strings to None
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"", "nan", "none", "null"}:
        return None

    return value


def to_title_case(value):
    """
    Convert a text value to title case.
    """

    value = clean_string(value)

    if value is None:
        return None

    return value.title()


def extract_number(value):
    """
    Extract the first numeric value from a text.

    Examples:
        '120 m²' -> 120
        '3 chambres' -> 3
        '2 salles de bain' -> 2
    """

    value = clean_string(value)

    if value is None:
        return None

    value = value.replace("\xa0", " ")

    match = re.search(r"(-?\d+(?:[.,]\d+)?)", value)

    if not match:
        return None

    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def extract_price(value):
    """
    Extract price from text.

    This function handles prices such as:
        '1 200 000 DH'
        '850000 DH'
        'Prix non spécifié'
    """

    value = clean_string(value)

    if value is None:
        return None

    lower_value = value.lower()

    if "prix non spécifié" in lower_value or "non spécifié" in lower_value:
        return None

    numbers = re.findall(r"\d+", value.replace("\xa0", " "))

    if not numbers:
        return None

    try:
        return float("".join(numbers))
    except ValueError:
        return None



# 5. STANDARDIZATION HELPERS


def standardize_city(city):
    """
    Standardize city names.
    """

    city = to_title_case(city)

    if city is None:
        return None

    replacements = {
        "Casa": "Casablanca",
        "Casablanca": "Casablanca",
        "Marrakesh": "Marrakech",
        "Marrakech": "Marrakech",
        "Agadir": "Agadir",
        "Rabat": "Rabat",
        "Sale": "Salé",
        "Salé": "Salé",
        "Tangier": "Tanger",
        "Tanger": "Tanger",
        "Fes": "Fès",
        "Fès": "Fès",
        "Meknes": "Meknès",
        "Meknès": "Meknès",
        "Tetouan": "Tétouan",
        "Tétouan": "Tétouan",
        "Kenitra": "Kénitra",
        "Kénitra": "Kénitra",
        "Temara": "Témara",
        "Témara": "Témara",
        "El Jadida": "El Jadida",
        "Mohammedia": "Mohammedia",
        "Essaouira": "Essaouira",
        "Oujda": "Oujda",
        "Ifrane": "Ifrane",
        "Benslimane": "Benslimane",
        "Dar Bouazza": "Dar Bouazza",
        "Mdiq": "M'Diq",
        "Mdik": "M'Diq",
    }

    return replacements.get(city, city)


def standardize_district(district):
    """
    Standardize district names.
    """

    district = to_title_case(district)

    if district is None:
        return None

    replacements = {
        "Maarif": "Maârif",
        "Maârif": "Maârif",
        "Ain Sebaa": "Aïn Sebaâ",
        "Aïn Sebaâ": "Aïn Sebaâ",
        "Gueliz": "Guéliz",
        "Guéliz": "Guéliz",
        "Semlalia": "Semlalia",
        "Hivernage": "Hivernage",
        "Agdal": "Agdal",
        "Racine": "Racine",
        "Bourgogne": "Bourgogne",
        "Hay Hassani": "Hay Hassani",
        "Sidi Maarouf": "Sidi Maarouf",
        "Hay Mohammadi": "Hay Mohammadi",
        "Californie": "Californie",
        "Tamraght": "Tamraght",
        "Ahlane": "Ahlane",
        "Taourirt": "Taourirt",
        "Hay Salam": "Hay Salam",
        "Palmier": "Palmier",
        "Route Jerada": "Route Jerada",
        "Hay El Andalous": "Hay El Andalous",
        "Andalous": "Andalous",
        "Toute La Ville": "Toute la ville",
    }

    return replacements.get(district, district)



# 6. FIELD PARSING FUNCTIONS


def parse_price(value):
    return extract_price(value)


def parse_surface(value):
    return extract_number(value)


def parse_rooms(value):
    return extract_number(value)


def parse_bathrooms(value):
    return extract_number(value)


def parse_floor(value):
    """
    Parse floor information.

    Examples:
        'Rez de chaussée' -> 0
        'Sous-sol' -> -1
        'Mezzanine' -> 0.5
        '3ème étage' -> 3
    """

    value = clean_string(value)

    if value is None:
        return None

    lower_value = value.lower()

    if "rez de chaussée" in lower_value or "rez de chaussee" in lower_value:
        return 0

    if "sous-sol" in lower_value or "sous sol" in lower_value:
        return -1

    if "mezzanine" in lower_value:
        return 0.5

    if "duplex" in lower_value:
        return None

    match = re.search(r"(-?\d+)", value)

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def parse_year(value):
    """
    Extract construction year.
    """

    value = clean_string(value)

    if value is None:
        return None

    match = re.search(r"(19\d{2}|20\d{2})", value)

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None



# 7. BUSINESS RULES


def apply_business_rules(df):
    """
    Apply logical validation rules.

    Invalid values are replaced with None.
    """

    current_year = datetime.now().year

    before_counts = {
        "price": df["price"].notna().sum(),
        "surface_m2": df["surface_m2"].notna().sum(),
        "rooms": df["rooms"].notna().sum(),
        "bathrooms": df["bathrooms"].notna().sum(),
        "floor": df["floor"].notna().sum(),
        "construction_year": df["construction_year"].notna().sum(),
    }

    df.loc[
        df["price"].notna()
        & ((df["price"] < 10_000) | (df["price"] > 100_000_000)),
        "price",
    ] = None

    df.loc[
        df["surface_m2"].notna()
        & ((df["surface_m2"] < 10) | (df["surface_m2"] > 1000)),
        "surface_m2",
    ] = None

    df.loc[
        df["rooms"].notna()
        & ((df["rooms"] < 0) | (df["rooms"] > 20)),
        "rooms",
    ] = None

    df.loc[
        df["bathrooms"].notna()
        & ((df["bathrooms"] < 0) | (df["bathrooms"] > 10)),
        "bathrooms",
    ] = None

    df.loc[
        df["floor"].notna()
        & ((df["floor"] < -5) | (df["floor"] > 100)),
        "floor",
    ] = None

    df.loc[
        df["construction_year"].notna()
        & (
            (df["construction_year"] < 1900)
            | (df["construction_year"] > current_year)
        ),
        "construction_year",
    ] = None

    after_counts = {
        "price": df["price"].notna().sum(),
        "surface_m2": df["surface_m2"].notna().sum(),
        "rooms": df["rooms"].notna().sum(),
        "bathrooms": df["bathrooms"].notna().sum(),
        "floor": df["floor"].notna().sum(),
        "construction_year": df["construction_year"].notna().sum(),
    }

    logger.info(
        "Business rules applied | "
        "price_removed=%s | surface_removed=%s | rooms_removed=%s | "
        "bathrooms_removed=%s | floor_removed=%s | year_removed=%s",
        before_counts["price"] - after_counts["price"],
        before_counts["surface_m2"] - after_counts["surface_m2"],
        before_counts["rooms"] - after_counts["rooms"],
        before_counts["bathrooms"] - after_counts["bathrooms"],
        before_counts["floor"] - after_counts["floor"],
        before_counts["construction_year"] - after_counts["construction_year"],
    )

    return df



# 8. LOAD RAW DATA


def load_bronze_file():
    """
    Load raw CSV file from the bronze layer.
    """

    if not BRONZE_FILE.exists():
        logger.error("Bronze file not found: %s", BRONZE_FILE)
        raise FileNotFoundError(f"Bronze file not found: {BRONZE_FILE}")

    df = pd.read_csv(BRONZE_FILE, encoding="utf-8-sig")

    logger.info(
        "Bronze file loaded successfully | rows=%s | path=%s",
        len(df),
        BRONZE_FILE,
    )

    return df



# 9. CLEAN DATAFRAME


def clean_dataframe(df):
    """
    Clean and transform raw listings into a structured dataset.
    """

    df = df.copy()

    df.columns = [str(col).strip() for col in df.columns]

    required_columns = {
        "Titre de l’annonce",
        "Prix",
        "Ville",
        "Quartier",
        "Surface (m²)",
        "Nombre de chambres",
        "Nombre de salles de bain",
        "Étage",
        "Année de construction",
        "Lien vers l’annonce",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        logger.error("Missing columns in raw CSV: %s", missing_columns)
        raise ValueError(f"Missing columns in raw CSV: {missing_columns}")

    for column in required_columns:
        df[column] = df[column].apply(clean_string)

    rows_before_duplicates = len(df)

    df = df.drop_duplicates(
        subset=["Lien vers l’annonce"],
        keep="first"
    )

    duplicates_removed = rows_before_duplicates - len(df)

    logger.info("Duplicates removed: %s", duplicates_removed)

    clean_df = pd.DataFrame()

    clean_df["title"] = df["Titre de l’annonce"].fillna("Annonce sans titre")
    clean_df["price"] = df["Prix"].apply(parse_price)
    clean_df["city"] = df["Ville"].apply(standardize_city)
    clean_df["district"] = df["Quartier"].apply(standardize_district)
    clean_df["surface_m2"] = df["Surface (m²)"].apply(parse_surface)
    clean_df["rooms"] = df["Nombre de chambres"].apply(parse_rooms)
    clean_df["bathrooms"] = df["Nombre de salles de bain"].apply(parse_bathrooms)
    clean_df["floor"] = df["Étage"].apply(parse_floor)
    clean_df["construction_year"] = df["Année de construction"].apply(parse_year)
    clean_df["listing_url"] = df["Lien vers l’annonce"]

    clean_df = apply_business_rules(clean_df)

    rows_before_url_filter = len(clean_df)

    clean_df = clean_df[
        clean_df["listing_url"].notna()
    ].copy()

    removed_without_url = rows_before_url_filter - len(clean_df)

    logger.info("Rows removed without listing URL: %s", removed_without_url)
    logger.info("Cleaning completed in memory | final_rows=%s", len(clean_df))

    return clean_df



# 10. SAVE CLEAN DATA


def save_to_csv(df):
    """
    Save cleaned data to CSV in the silver layer.
    """

    df.to_csv(
        SILVER_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    logger.info(
        "Clean CSV saved successfully | rows=%s | path=%s",
        len(df),
        SILVER_FILE,
    )


def save_to_database(df):
    """
    Save cleaned data to PostgreSQL.
    """

    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS clean"))
        conn.execute(text("DROP TABLE IF EXISTS clean.clean_listings"))

    df.to_sql(
        "clean_listings",
        engine,
        schema="clean",
        if_exists="replace",
        index=False,
        method="multi",
    )

    logger.info(
        "Data saved to PostgreSQL successfully | table=clean.clean_listings | rows=%s",
        len(df),
    )



# 11. MAIN PIPELINE

def main():
    """
    Run the complete cleaning pipeline.
    """

    logger.info("=" * 80)
    logger.info("STARTING CLEANING PIPELINE")
    logger.info("=" * 80)

    try:
        raw_df = load_bronze_file()

        logger.info("Rows before cleaning: %s", len(raw_df))

        clean_df = clean_dataframe(raw_df)

        logger.info("Rows after cleaning: %s", len(clean_df))

        if clean_df.empty:
            logger.warning("No cleaned rows produced. Pipeline stopped.")
            return

        save_to_csv(clean_df)
        save_to_database(clean_df)

        logger.info("=" * 80)
        logger.info("CLEANING PIPELINE FINISHED SUCCESSFULLY")
        logger.info("=" * 80)

    except Exception as error:
        logger.exception("Cleaning pipeline failed: %s", error)
        raise



# 12. SCRIPT ENTRY POINT


if __name__ == "__main__":
    main()