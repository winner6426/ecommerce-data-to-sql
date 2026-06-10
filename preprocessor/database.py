import sqlite3

import pandas as pd

from .config import MARKETPLACE_DB_FILE


def write_database(
    categories_df: pd.DataFrame,
    listings_df: pd.DataFrame,
    attributes_df: pd.DataFrame,
    detail_frames: dict[str, pd.DataFrame],
) -> None:
    with sqlite3.connect(MARKETPLACE_DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        categories_df.to_sql("categories", conn, if_exists="replace", index=False)
        listings_df.to_sql("listings", conn, if_exists="replace", index=False)
        attributes_df.to_sql("listing_attributes", conn, if_exists="replace", index=False)
        for table_name, df in detail_frames.items():
            df.to_sql(table_name, conn, if_exists="replace", index=False)

        conn.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_category_id ON categories(category_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_listings_list_id ON listings(list_id);
            CREATE INDEX IF NOT EXISTS idx_listings_category_id ON listings(category_id);
            CREATE INDEX IF NOT EXISTS idx_listings_root_category_id ON listings(root_category_id);
            CREATE INDEX IF NOT EXISTS idx_listings_partition ON listings(partition_category_id, partition_date);
            CREATE INDEX IF NOT EXISTS idx_listings_location ON listings(region_name, area_name, ward_name);
            CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
            CREATE INDEX IF NOT EXISTS idx_attributes_list_id ON listing_attributes(list_id);
            CREATE INDEX IF NOT EXISTS idx_attributes_id ON listing_attributes(attribute_id);

            DROP VIEW IF EXISTS listings_enriched;
            CREATE VIEW listings_enriched AS
            SELECT
                l.list_id,
                l.ad_id,
                l.category_id,
                l.root_category_id,
                l.partition_category_id,
                l.partition_date,
                COALESCE(c.category_name, l.category_name) AS root_category_name,
                l.category_name AS subcategory_name,
                l.category_group,
                l.title,
                l.price,
                l.price_text,
                l.region_name,
                l.area_name,
                l.ward_name,
                l.seller_name,
                l.company_ad,
                l.date_text,
                l.list_time
            FROM listings l
            LEFT JOIN categories c ON c.category_id = l.root_category_id;

            DROP VIEW IF EXISTS real_estate_listings;
            CREATE VIEW real_estate_listings AS
            SELECT
                l.*,
                d.property_type,
                d.listing_type,
                d.area_m2,
                d.rooms,
                d.toilets,
                d.floors,
                d.legal_document,
                d.price_per_m2,
                d.area_group,
                d.price_group
            FROM listings_enriched l
            JOIN real_estate_details d ON d.list_id = l.list_id;
            """
        )
