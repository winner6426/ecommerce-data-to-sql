import json
import time
import logging
from pathlib import Path
from datetime import datetime

import requests

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
LOG_DIR = HERE / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

ID_FILE = DATA_DIR / "all_ids.json"
RAW_FILE = DATA_DIR / "all_raw_data.json"
LOG_FILE = LOG_DIR / "crawler.log"

REGION_V2 = 12000
CATEGORY = 1000
PAGE_START = 0
PAGE_END = 20
LIMIT = 20

SLEEP_LIST = 1.5
SLEEP_DETAIL = 0.8

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, obj):
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def safe_get(url, retries=3, sleep=2):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            return r

        except requests.HTTPError:
            raise

        except Exception as e:
            msg = f"Request lỗi lần {attempt}/{retries}: {e}"
            print(msg)
            logging.warning(msg)
            time.sleep(sleep)

    raise Exception(f"Request thất bại sau {retries} lần: {url}")


def get_ad_ids(page: int) -> list:
    offset = page * LIMIT

    url = (
        "https://gateway.chotot.com/v1/public/ad-listing"
        f"?region_v2={REGION_V2}&cg={CATEGORY}&o={offset}&limit={LIMIT}"
    )

    r = safe_get(url)

    return [
        ad["list_id"]
        for ad in r.json().get("ads", [])
        if "list_id" in ad
    ]


def crawl_detail(ad_id) -> dict:
    url = f"https://gateway.chotot.com/v1/public/ad-listing/{ad_id}"
    r = safe_get(url)
    return r.json()


def step_collect_ids() -> set:
    all_ids = set(load_json(ID_FILE, []))

    print(f"[IDs] load sẵn: {len(all_ids)}")
    logging.info(f"Loaded ids: {len(all_ids)}")

    for page in range(PAGE_START, PAGE_END):
        try:
            ids = get_ad_ids(page)

        except Exception as e:
            msg = f"[IDs] page {page + 1} lỗi: {e}"
            print(msg)
            logging.error(msg)
            time.sleep(SLEEP_LIST * 2)
            continue

        before = len(all_ids)
        all_ids.update(ids)

        msg = f"[IDs] page {page + 1}: +{len(all_ids) - before} mới, tổng {len(all_ids)}"
        print(msg)
        logging.info(msg)

        time.sleep(SLEEP_LIST)

    save_json(ID_FILE, sorted(list(all_ids)))

    return all_ids


def step_crawl_details(all_ids: set) -> dict:
    raw = load_json(RAW_FILE, {})
    crawled = set(raw.keys())

    todo = [
        str(x)
        for x in all_ids
        if str(x) not in crawled
    ]

    print(f"[RAW] đã có {len(crawled)} records")
    print(f"[RAW] cần crawl thêm: {len(todo)}")

    logging.info(f"Existing raw records: {len(crawled)}")
    logging.info(f"Need crawl: {len(todo)}")

    for i, ad_id in enumerate(todo, 1):
        try:
            data = crawl_detail(ad_id)

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                msg = f"[RAW] 404 bỏ qua {ad_id}"
                print(msg)
                logging.warning(msg)

                all_ids.discard(int(ad_id)) if ad_id.isdigit() else all_ids.discard(ad_id)
                continue

            msg = f"[RAW] HTTP error {ad_id}: {e}"
            print(msg)
            logging.error(msg)
            continue

        except Exception as e:
            msg = f"[RAW] lỗi {ad_id}: {e}"
            print(msg)
            logging.error(msg)
            continue

        raw[ad_id] = data

        if i % 20 == 0:
            save_json(RAW_FILE, raw)
            save_json(ID_FILE, sorted(list(all_ids)))

            msg = f"[RAW] checkpoint {i}/{len(todo)}, tổng lưu {len(raw)}"
            print(msg)
            logging.info(msg)

        time.sleep(SLEEP_DETAIL)

    save_json(RAW_FILE, raw)
    save_json(ID_FILE, sorted(list(all_ids)))

    print(f"[RAW] hoàn tất: {len(raw)} records")
    logging.info(f"Finished raw records: {len(raw)}")

    return raw


def main():
    print("=" * 60)
    print("CRAWL NHATOT / CHOTOT")
    print("=" * 60)

    logging.info("=" * 60)
    logging.info(f"START CRAWLER at {datetime.now()}")
    logging.info("=" * 60)

    all_ids = step_collect_ids()
    step_crawl_details(all_ids)

    print("\n" + "=" * 60)
    print("START PREPROCESSING")
    print("=" * 60)

    import preprocess
    preprocess.main()

    print("\nPIPELINE COMPLETED!")
    logging.info("PIPELINE COMPLETED")


if __name__ == "__main__":
    main()