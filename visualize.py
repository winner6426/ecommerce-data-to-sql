import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path


DATA_DIR = Path("data")
OUTPUT_DIR = Path("charts")

OUTPUT_DIR.mkdir(exist_ok=True)

CSV_FILE = DATA_DIR / "cleaned_data.csv"


def main():

    df = pd.read_csv(CSV_FILE)

    print(df.head())

    # =========================
    # TOP DISTRICTS
    # =========================

    top_districts = (
        df.groupby("district")["price_per_m2"]
        .mean()
        .sort_values(ascending=False)
        .head(10)
    )

    plt.figure(figsize=(12, 6))

    top_districts.plot(kind="bar")

    plt.title("Top 10 Districts by Average Price per m2")

    plt.ylabel("Price per m2")

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "top_districts.png"
    )

    plt.close()

    # =========================
    # AREA DISTRIBUTION
    # =========================

    plt.figure(figsize=(10, 6))

    df["area"].hist(bins=30)

    plt.title("Area Distribution")

    plt.xlabel("Area (m2)")

    plt.ylabel("Count")

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "area_distribution.png"
    )

    plt.close()

    # =========================
    # PRICE DISTRIBUTION
    # =========================

    plt.figure(figsize=(10, 6))

    df["price_billion"].hist(bins=30)

    plt.title("Price Distribution (Billion VND)")

    plt.xlabel("Price (Billion VND)")

    plt.ylabel("Count")

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "price_distribution.png"
    )

    plt.close()

    # =========================
    # PROPERTY TYPE COUNT
    # =========================

    property_counts = (
        df["property_type"]
        .value_counts()
        .head(10)
    )

    plt.figure(figsize=(12, 6))

    property_counts.plot(kind="bar")

    plt.title("Property Type Count")

    plt.ylabel("Count")

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "property_types.png"
    )

    plt.close()

    print("\nSaved charts to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()