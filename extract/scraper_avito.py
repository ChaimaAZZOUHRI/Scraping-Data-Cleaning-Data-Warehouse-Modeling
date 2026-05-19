import os
import time
import csv
import re
import random
import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



# SETTINGS

TARGET_ROWS = 900
MAX_PAGES = 80

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "bronze" / "raw_listings.csv"
LOG_DIR = PROJECT_ROOT / "logs"

BASE_URL = "https://www.avito.ma/fr/maroc/appartements-%C3%A0_vendre?rooms=1&bathrooms=1&has_price=true&price=100000-"


# LOGGING

LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "scraper_avito.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)



# DRIVER

def create_driver():
    options = webdriver.ChromeOptions()

    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-allow-origins=*")
    # options.add_argument("--headless=new")  # uncomment later if needed

    driver = webdriver.Chrome(options=options)
    return driver



# PAGE URL

def build_page_url(page):
    if page == 1:
        return BASE_URL
    return BASE_URL + f"&o={page}"



# HELPERS

def split_location(location_text):
    """
    Expected:
    'Appartements dans Marrakech, Semlalia'
    Returns:
    ville='Marrakech', quartier='Semlalia'
    """
    if not location_text:
        return "", ""

    location_text = re.sub(r"^Appartements?\s+dans\s+", "", location_text, flags=re.IGNORECASE).strip()
    parts = [p.strip() for p in location_text.split(",") if p.strip()]

    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ""
    return "", ""


def extract_floor(text):
    if not text:
        return ""

    match = re.search(r"(?:Étage|Etage|étage|etage)\s*(\d+)", text, flags=re.IGNORECASE)
    if match:
        return f"Étage {match.group(1)}"

    if re.search(r"rez de chaussée|rez de chaussee", text, flags=re.IGNORECASE):
        return "Rez de chaussée"

    return ""


def extract_year(text):
    if not text:
        return None

    match = re.search(r"(19\d{2}|20\d{2})", text)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def normalize_price(price):
    if price is None:
        return ""
    return f"{price} DH"


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()



# LOAD EXISTING LINKS

def load_existing_links(file=OUTPUT_FILE):
    existing_links = set()

    if not os.path.isfile(file):
        return existing_links

    try:
        with open(file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                link = row.get("Lien vers l’annonce")
                if link:
                    existing_links.add(link)

    except Exception as e:
        logging.warning(f"Could not read existing CSV: {e}")

    return existing_links



# COUNT EXISTING ROWS

def count_existing_rows(file=OUTPUT_FILE):
    if not os.path.isfile(file):
        return 0

    try:
        with open(file, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)

    except Exception:
        return 0



# SAVE

def save(data, file=OUTPUT_FILE):
    if not data:
        return

    os.makedirs(os.path.dirname(file), exist_ok=True)
    file_exists = os.path.isfile(file)

    fieldnames = [
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
    ]

    with open(file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerows(data)

    logging.info(f"{len(data)} new rows saved in {file}")



# PRINT RESULT IN TERMINAL + LOG FILE

def print_result(row, total_count):
    logging.info(
        f"[{total_count}/{TARGET_ROWS}] "
        f"TITRE: {row['Titre de l’annonce']} | "
        f"PRIX: {row['Prix']} | "
        f"VILLE: {row['Ville']} | "
        f"QUARTIER: {row['Quartier']} | "
        f"SURFACE: {row['Surface (m²)']} | "
        f"CHAMBRES: {row['Nombre de chambres']} | "
        f"SDB: {row['Nombre de salles de bain']} | "
        f"ETAGE: {row['Étage']} | "
        f"ANNEE: {row['Année de construction']} | "
        f"LINK: {row['Lien vers l’annonce']}"
    )



# SAFE DRIVER CHECK

def driver_is_alive(driver):
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False



# RESTART DRIVER

def restart_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass

    logging.warning("Restarting Chrome driver...")
    driver = create_driver()
    time.sleep(3)

    return driver


# SCRAPE ONE CARD

def scrape_card(card):
    text = card.text

    # -------- TITLE --------
    title = ""
    try:
        title = card.find_element(By.CSS_SELECTOR, "p[title]").text.strip()
    except Exception:
        pass

    # -------- PRICE --------
    price = None
    try:
        price_element = card.find_element(By.CSS_SELECTOR, "span.sc-3286ebc5-2.PuYkS")
        price_text = price_element.get_attribute("textContent")
        price_text = re.sub(r"[^\d]", "", price_text)

        if price_text:
            price = int(price_text)
    except Exception:
        pass

    # -------- LOCATION --------
    location = ""
    if "dans" in text:
        location_lines = [line for line in text.split("\n") if "dans" in line]
        location = location_lines[0].strip() if location_lines else ""

    ville, quartier = split_location(location)

    # -------- DETAILS --------
    surface = None
    rooms = None
    baths = None
    floor = ""
    construction_year = None

    for line in text.split("\n"):
        line_clean = line.strip()
        line_lower = line_clean.lower()

        if "m²" in line_clean or "m2" in line_lower:
            surface = line_clean

        if "chambre" in line_lower:
            rooms = line_clean

        if "sdb" in line_lower or "bain" in line_lower:
            baths = line_clean

        if "étage" in line_lower or "etage" in line_lower or "rez de chaussée" in line_lower:
            floor = extract_floor(line_clean)

        year_found = extract_year(line_clean)
        if year_found:
            construction_year = year_found

    link = card.get_attribute("href")

    return {
        "Titre de l’annonce": clean_text(title),
        "Prix": normalize_price(price),
        "Ville": clean_text(ville),
        "Quartier": clean_text(quartier),
        "Surface (m²)": clean_text(surface),
        "Nombre de chambres": clean_text(rooms),
        "Nombre de salles de bain": clean_text(baths),
        "Étage": clean_text(floor),
        "Année de construction": construction_year,
        "Lien vers l’annonce": clean_text(link),
    }


# MAIN

def main():
    existing_links = load_existing_links()
    total_saved = count_existing_rows()

    logging.info("=" * 80)
    logging.info("START SCRAPING")
    logging.info(f"Existing rows in CSV: {total_saved}")
    logging.info(f"Target rows: {TARGET_ROWS}")
    logging.info("=" * 80)

    if total_saved >= TARGET_ROWS:
        logging.info("Target already reached. No scraping needed.")
        return

    driver = create_driver()
    buffer = []

    for page in range(1, MAX_PAGES + 1):
        if total_saved >= TARGET_ROWS:
            break

        page_url = build_page_url(page)

        logging.info("=" * 80)
        logging.info(f"OPENING PAGE {page}: {page_url}")
        logging.info("=" * 80)

        try:
            if not driver_is_alive(driver):
                driver = restart_driver(driver)

            driver.get(page_url)

            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            time.sleep(random.uniform(3, 5))

        except Exception as e:
            logging.warning(f"PAGE LOAD ERROR: {e}")
            driver = restart_driver(driver)
            continue

        # Scroll page
        try:
            for _ in range(5):
                driver.execute_script("window.scrollBy(0,1200)")
                time.sleep(random.uniform(1, 2))

        except NoSuchWindowException:
            logging.warning("Chrome window closed during scrolling.")
            driver = restart_driver(driver)
            continue

        except WebDriverException as e:
            logging.warning(f"SCROLL ERROR: {e}")
            driver = restart_driver(driver)
            continue

        # Find cards
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/appartements/']")
            logging.info(f"{len(cards)} cards found on page {page}")

        except Exception as e:
            logging.warning(f"CARD FIND ERROR: {e}")
            continue

        if not cards:
            logging.warning(f"No cards found on page {page}")
            continue

        for card in cards:
            if total_saved >= TARGET_ROWS:
                break

            try:
                row = scrape_card(card)
                link = row.get("Lien vers l’annonce")

                if not link:
                    continue

                if link in existing_links:
                    continue

                existing_links.add(link)
                buffer.append(row)
                total_saved += 1

                print_result(row, total_saved)

                # Save every 20 rows
                if len(buffer) >= 20:
                    save(buffer)
                    buffer = []

            except Exception as e:
                logging.warning(f"AD ERROR: {e}")

        time.sleep(random.uniform(3, 6))

        # Restart driver every 10 pages
        if page % 10 == 0:
            driver = restart_driver(driver)

    # Final save
    if buffer:
        save(buffer)

    try:
        driver.quit()
    except Exception:
        pass

    logging.info("=" * 80)
    logging.info(f"SCRAPING FINISHED. TOTAL ROWS IN CSV: {count_existing_rows()}")
    logging.info("=" * 80)



# RUN

if __name__ == "__main__":
    main()