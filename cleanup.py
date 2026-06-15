from __future__ import annotations

import argparse 
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path("data")
PARTITION_ROOTS = [DATA_DIR / "raw", DATA_DIR / "clean"]

def parse_partition_date(path: Path) -> date | None:
    for part in path.parts:
        if part.startswith("date="):
            value = part.split("=", 1)[1]
            try: 
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None
    return None

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true") #test
    args = parser.parse_args()

    cutoff = date.today() - timedelta(days=args.keep_days)

    deleted = 0
    for root in PARTITION_ROOTS:
        if not root.exists():
            continue
        
        for partition_dir in root.glob("category_id=*/date=*/"):
            if not partition_dir.is_dir():
                continue

            partition_date = parse_partition_date(partition_dir)
            if partition_date is None:
                continue

            if partition_date < cutoff:
                print(f"Delete: {partition_dir}")
                deleted += 1

                if not args.dry_run:
                    shutil.rmtree(partition_dir)


    print(f"Total partitions deleted: {deleted}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())