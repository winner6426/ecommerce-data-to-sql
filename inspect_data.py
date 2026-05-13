import json

with open("data/all_raw_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Tổng số records:", len(data))

# lấy key đầu tiên
first_key = list(data.keys())[0]

print("\n===== SAMPLE RECORD =====\n")

print(data[first_key])