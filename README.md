# Ecommerce Data to SQL

Pipeline crawl du lieu Chotot/Nhatot, lam sach thanh lakehouse/SQLite, roi hoi du lieu bang Text2SQL agent chay Vertex AI.

## Setup

```bat
pip install -r requirements.txt
```

Tao/cap nhat `.env` o root:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1
TEXT2SQL_MODEL=gemini-2.5-flash
TEXT2SQL_DB_PATH=data/marketplace.db
```

Dang nhap Google Cloud neu dung Vertex AI:

```bat
gcloud auth application-default login
gcloud config set project your-gcp-project
```

## Crawl

```bat
python crawler/main.py
```

Test it trang:

```bat
python crawler/main.py --page-end 1
```

Raw JSON:

```text
data/raw/category_id=<id>/date=<yyyy-mm-dd>/listings.json
```

## Preprocess

```bat
python preprocessor/main.py
```

Output:

```text
data/clean/category_id=<id>/date=<yyyy-mm-dd>/*.csv
data/marketplace.db
```

## Text2SQL Agent

```bat
python -m text2sql.cli "Co bao nhieu tin bat dong san o Ha Noi?"
```

Cau phuc tap nen tang so vong:

```bat
python -m text2sql.cli "O Ha Noi, moi hang xe co bao nhieu tin dang?" --max-rounds 12
```

API server:

```bat
python -m uvicorn text2sql.server:app --host 0.0.0.0 --port 8010 --reload
```

## SQLite Tables

DB chinh: `data/marketplace.db`

- `listings`: bang trung tam cho tin dang.
- `categories`: danh muc.
- `listing_attributes`: thuoc tinh bo sung dang key-value.
- `real_estate_details`: bat dong san.
- `vehicle_details`: xe.
- `electronics_details`: dien tu.
- `product_details`: san pham khac.
- `job_details`: viec lam.
- `service_details`: dich vu.
- `pet_details`: thu cung.
