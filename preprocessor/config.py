from pathlib import Path


DATA_DIR = Path("data")
LOG_DIR = Path("logs")

RAW_LAKE_DIR = DATA_DIR / "raw"
CLEAN_LAKE_DIR = DATA_DIR / "clean"

CATEGORY_FILE = DATA_DIR / "cat_id.json"
MARKETPLACE_DB_FILE = DATA_DIR / "marketplace.db"
LOG_FILE = LOG_DIR / "preprocess.log"

REAL_ESTATE_CATEGORIES = {1000}
VEHICLE_CATEGORIES = {2000}
JOB_CATEGORIES = {13000}
SERVICE_CATEGORIES = {6000, 15000}
ELECTRONICS_CATEGORIES = {5000, 9000}
PET_CATEGORIES = {12000}

DETAIL_COLUMNS = {
    "real_estate_details": [
        "list_id",
        "property_type",
        "listing_type",
        "area_m2",
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
        "condition",
    ],
    "job_details": [
        "list_id",
        "job_type",
        "job_title",
        "company_name",
        "salary_min",
        "salary_max",
        "salary_text",
        "contract_type",
        "preferred_gender",
        "experience",
        "work_location",
        "urgent",
    ],
    "product_details": [
        "list_id",
        "product_type",
        "condition",
        "item_detail",
    ],
    "electronics_details": [
        "list_id",
        "electronics_type",
        "brand",
        "model",
        "condition",
        "warranty",
        "capacity",
    ],
    "pet_details": [
        "list_id",
        "pet_type",
        "breed",
        "age",
    ],
    "service_details": [
        "list_id",
        "service_type",
        "price_unit",
        "min_price",
    ],
}
