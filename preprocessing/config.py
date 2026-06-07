from pathlib import Path


DATA_DIR = Path("data")
LOG_DIR = Path("logs")

RAW_LAKE_DIR = DATA_DIR / "raw"
CLEAN_LAKE_DIR = DATA_DIR / "clean"

LEGACY_RAW_FILE = DATA_DIR / "all_raw_data.json"
LEGACY_ID_FILE = DATA_DIR / "all_ids.json"
LEGACY_ID_BY_CATEGORY_FILE = DATA_DIR / "all_ids_by_category.json"

CATEGORY_FILE = DATA_DIR / "cat_id.json"
MARKETPLACE_DB_FILE = DATA_DIR / "marketplace.db"
LEGACY_DB_FILE = DATA_DIR / "real_estate.db"
LOG_FILE = LOG_DIR / "preprocess.log"

AGG_LISTINGS_CSV = DATA_DIR / "cleaned_listings.csv"
AGG_ATTRIBUTES_CSV = DATA_DIR / "listing_attributes.csv"

REAL_ESTATE_CATEGORIES = {1000}
VEHICLE_CATEGORIES = {2000}
JOB_CATEGORIES = {13000}
SERVICE_CATEGORIES = {6000, 15000}

DETAIL_COLUMNS = {
    "real_estate_details": [
        "list_id",
        "property_type",
        "listing_type",
        "area_m2",
        "living_area_m2",
        "width_m",
        "length_m",
        "rooms",
        "toilets",
        "floors",
        "legal_document",
        "furnishing",
        "street_name",
        "price_per_m2",
        "area_group",
        "price_group",
    ],
    "vehicle_details": [
        "list_id",
        "vehicle_type",
        "brand",
        "model",
        "year",
        "mileage_km",
        "fuel",
        "transmission",
        "condition",
        "color",
        "origin",
    ],
    "job_details": [
        "list_id",
        "job_type",
        "position",
        "company_name",
        "salary_min",
        "salary_max",
        "salary_text",
        "experience",
        "education",
        "gender",
        "work_location",
    ],
    "product_details": [
        "list_id",
        "product_type",
        "brand",
        "model",
        "condition",
        "warranty",
        "color",
        "origin",
    ],
    "service_details": [
        "list_id",
        "service_type",
        "provider_type",
        "price_unit",
    ],
}
