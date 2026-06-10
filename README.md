# Ecommerce Data to SQL

Pipeline crawl Chotot/Nhatot, luu file theo lakehouse layout, preprocess theo category, va tao SQLite database dung cho text-to-SQL.

## Crawl

Crawl tat ca category trong `data/cat_id.json`:

```bash
python Crawler/crawl.py
```

Crawl mot vai category cu the:

```bash
python Crawler/crawl.py --categories 1000 2000 13000 --page-end 5
```

Raw JSON duoc luu theo partition:

```text
data/raw/category_id=<root_category_id>/date=<yyyy-mm-dd>/listings.json
```

Crawler van giu cac cache sau de tiep tuc crawl nhanh hon:

- `data/all_ids.json`
- `data/all_ids_by_category.json`
- `data/all_raw_data.json`

## Preprocess

```bash
python preprocess.py
```

Clean CSV duoc luu theo partition:

```text
data/clean/category_id=<root_category_id>/date=<yyyy-mm-dd>/listings.csv
data/clean/category_id=<root_category_id>/date=<yyyy-mm-dd>/listing_attributes.csv
data/clean/category_id=<root_category_id>/date=<yyyy-mm-dd>/*_details.csv
```

Neu chua co `data/raw/...`, preprocess se migrate tu `data/all_raw_data.json` sang lakehouse raw truoc.

## SQLite Schema

Database chinh: `data/marketplace.db`.

Bang chinh:

- `categories`: root category tu `cat_id.json`.
- `listings`: bang chung cho moi listing, khong chia bang theo category.
- `listing_attributes`: key-value attributes tu raw `params`.
- `real_estate_details`: cot dac thu bat dong san.
- `vehicle_details`: cot dac thu xe.
- `job_details`: cot dac thu viec lam.
- `product_details`: cot dac thu cac nhom hang hoa con lai.
- `service_details`: cot dac thu dich vu.

Cot category quan trong trong `listings`:

- `category_id`: category/subcategory goc tu listing.
- `root_category_id`: category goc de join voi `categories`.
- `partition_category_id`: category cua file lakehouse.
- `partition_date`: ngay cua file lakehouse.

Views tien dung cho text-to-SQL:

- `listings_enriched`
- `real_estate_listings`

## Preprocess Modules

- `preprocess.py`: entrypoint.
- `preprocessing/config.py`: duong dan, category group, schema cot detail.
- `preprocessing/utils.py`: helper convert type, text, category group, params.
- `preprocessing/lakehouse.py`: doc/ghi raw va clean lakehouse.
- `preprocessing/transformers.py`: chuyen raw JSON thanh DataFrame chuan.
- `preprocessing/database.py`: ghi SQLite, indexes, views.
- `preprocessing/pipeline.py`: orchestration.

## Current Data Check

Raw hien tai co 788 records, tat ca thuoc `root_category_id=1000` Bat dong san. Khi crawl them category khac, pipeline se tao them partition trong `data/raw`, `data/clean`, va dien du lieu vao cac bang detail tuong ung.
