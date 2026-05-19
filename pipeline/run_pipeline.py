import subprocess
import sys
import time
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# =========================================================
# PATHS
# =========================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "pipeline.log"


# =========================================================
# SETTINGS
# =========================================================
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 5
CLEAN_STAGING_AFTER_SUCCESS = False


# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# =========================================================
# ENV / DB
# =========================================================
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


# =========================================================
# PYTHON STEP
# =========================================================
def run_python_step(step_name, script_path):
    if not script_path.exists():
        logger.error("Missing Python script: %s", script_path)
        raise FileNotFoundError(f"Missing Python script: {script_path}")

    for attempt in range(1, MAX_RETRIES + 2):
        logger.info("=" * 80)
        logger.info("RUNNING PYTHON STEP: %s | Attempt %s", step_name, attempt)
        logger.info("SCRIPT PATH: %s", script_path)
        logger.info("=" * 80)

        print("=" * 80)
        print(f"RUNNING: {step_name} | Attempt {attempt}")
        print(f"PYTHON SCRIPT: {script_path}")
        print("=" * 80)

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True
        )

        if result.stdout:
            logger.info("STDOUT for %s:\n%s", step_name, result.stdout)

        if result.stderr:
            logger.error("STDERR for %s:\n%s", step_name, result.stderr)

        if result.returncode == 0:
            logger.info("FINISHED PYTHON STEP: %s", step_name)
            print(f"FINISHED: {step_name}\n")
            return

        logger.error(
            "PYTHON STEP FAILED: %s | attempt=%s | return code=%s",
            step_name,
            attempt,
            result.returncode
        )

        if attempt <= MAX_RETRIES:
            logger.info("Retrying %s after %s seconds...", step_name, RETRY_DELAY_SECONDS)
            time.sleep(RETRY_DELAY_SECONDS)
        else:
            raise RuntimeError(f"Step failed after {attempt} attempts: {step_name}")


# =========================================================
# SQL STEP
# =========================================================
def run_sql_step(step_name, sql_path):
    if not sql_path.exists():
        logger.error("Missing SQL file: %s", sql_path)
        raise FileNotFoundError(f"Missing SQL file: {sql_path}")

    for attempt in range(1, MAX_RETRIES + 2):
        logger.info("=" * 80)
        logger.info("RUNNING SQL STEP: %s | Attempt %s", step_name, attempt)
        logger.info("SQL PATH: %s", sql_path)
        logger.info("=" * 80)

        print("=" * 80)
        print(f"RUNNING: {step_name} | Attempt {attempt}")
        print(f"SQL FILE: {sql_path}")
        print("=" * 80)

        try:
            sql_content = sql_path.read_text(encoding="utf-8")

            statements = []
            for stmt in sql_content.split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    statements.append(stmt)

            engine = get_engine()

            with engine.begin() as conn:
                for i, stmt in enumerate(statements, start=1):
                    try:
                        conn.execute(text(stmt))
                    except Exception as stmt_error:
                        logger.exception(
                            "FAILED SQL STATEMENT | step=%s | attempt=%s | statement_number=%s | statement=%s | error=%s",
                            step_name,
                            attempt,
                            i,
                            stmt,
                            stmt_error,
                        )
                        print(f"\nSQL ERROR in {step_name}")
                        print(f"Statement number: {i}")
                        print(f"Statement:\n{stmt}\n")
                        print(f"Error: {stmt_error}\n")
                        raise

            logger.info("FINISHED SQL STEP: %s", step_name)
            print(f"FINISHED: {step_name}\n")
            return

        except Exception as e:
            logger.exception(
                "SQL STEP FAILED: %s | attempt=%s | error=%s",
                step_name,
                attempt,
                e,
            )
            print(f"SQL STEP FAILED in {step_name}: {e}")

            if attempt <= MAX_RETRIES:
                logger.info(
                    "Retrying %s after %s seconds...",
                    step_name,
                    RETRY_DELAY_SECONDS,
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                raise RuntimeError(
                    f"SQL step failed after {attempt} attempts: {step_name}"
                ) from e
# VALIDATION

def validate_warehouse():
    logger.info("=" * 80)
    logger.info("STARTING FINAL VALIDATION")
    logger.info("=" * 80)

    engine = get_engine()

    queries = {
        "staging_count": "SELECT COUNT(*) FROM staging.raw_listings;",
        "clean_count": "SELECT COUNT(*) FROM clean.clean_listings;",
        "bi_fact_count": "SELECT COUNT(*) FROM bi_schema.fact_listings;",
        "ml_count": "SELECT COUNT(*) FROM ml_schema.ml_ready_listings;",
        "orphan_time": """
            SELECT COUNT(*)
            FROM bi_schema.fact_listings f
            LEFT JOIN bi_schema.dim_time t ON f.time_id = t.time_id
            WHERE t.time_id IS NULL;
        """,
        "orphan_location": """
            SELECT COUNT(*)
            FROM bi_schema.fact_listings f
            LEFT JOIN bi_schema.dim_location l ON f.location_id = l.location_id
            WHERE l.location_id IS NULL;
        """,
        "orphan_property": """
            SELECT COUNT(*)
            FROM bi_schema.fact_listings f
            LEFT JOIN bi_schema.dim_property p ON f.property_id = p.property_id
            WHERE p.property_id IS NULL;
        """,
    }

    results = {}

    with engine.begin() as conn:
        for key, query in queries.items():
            value = conn.execute(text(query)).scalar()
            results[key] = value
            logger.info("%s = %s", key, value)
            print(f"{key}: {value}")

    if results["clean_count"] == 0:
        raise RuntimeError("Validation failed: clean.clean_listings is empty")

    if results["bi_fact_count"] == 0:
        raise RuntimeError("Validation failed: bi_schema.fact_listings is empty")

    if results["ml_count"] == 0:
        raise RuntimeError("Validation failed: ml_schema.ml_ready_listings is empty")

    if results["orphan_time"] != 0:
        raise RuntimeError("Validation failed: orphan rows in dim_time relation")

    if results["orphan_location"] != 0:
        raise RuntimeError("Validation failed: orphan rows in dim_location relation")

    if results["orphan_property"] != 0:
        raise RuntimeError("Validation failed: orphan rows in dim_property relation")
# =========================================================

    logger.info("FINAL VALIDATION PASSED")
    print("FINAL VALIDATION PASSED")


# =========================================================
# STAGING CLEANUP
# =========================================================
def cleanup_staging():
    logger.info("Cleaning staging.raw_listings after successful pipeline run")
    print("Cleaning staging.raw_listings ...")

    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE staging.raw_listings;"))

    logger.info("staging.raw_listings cleaned successfully")
    print("staging.raw_listings cleaned successfully")


# =========================================================
# MAIN
# =========================================================
def main():
    steps = [
        ("Create staging tables", "sql", PROJECT_ROOT / "staging" / "create_staging_tables.sql"),
        ("Scraping", "python", PROJECT_ROOT / "extract" / "scraper_avito.py"),
        ("Load raw to staging", "python", PROJECT_ROOT / "staging" / "load_raw_to_staging.py"),
        ("Cleaning", "python", PROJECT_ROOT / "clean" / "cleaning.py"),
        ("Feature engineering", "python", PROJECT_ROOT / "clean" / "feature_engineering.py"),
        ("Create BI schema", "sql", PROJECT_ROOT / "warehouse" / "create_bi_schema.sql"),
        ("Create ML schema", "sql", PROJECT_ROOT / "warehouse" / "create_ml_schema.sql"),
        ("Load warehouse", "python", PROJECT_ROOT / "warehouse" / "load_warehouse.py"),
    ]

    logger.info("=" * 80)
    logger.info("STARTING FULL PIPELINE")
    logger.info("=" * 80)

    print("=" * 80)
    print("STARTING FULL PIPELINE")
    print("=" * 80)

    for step_name, step_type, step_path in steps:
        if step_type == "python":
            run_python_step(step_name, step_path)
        elif step_type == "sql":
            run_sql_step(step_name, step_path)
        else:
            raise ValueError(f"Unknown step type: {step_type}")

    validate_warehouse()

    if CLEAN_STAGING_AFTER_SUCCESS:
        cleanup_staging()
    else:
        logger.info("Staging kept for reuse")
        print("Staging kept for reuse")

    logger.info("=" * 80)
    logger.info("PIPELINE EXECUTED SUCCESSFULLY")
    logger.info("=" * 80)

    print("=" * 80)
    print("PIPELINE EXECUTED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()