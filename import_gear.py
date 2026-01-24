# import_gear.py
import csv
import sqlite3
from config import DATABASE


def clean(val):
    if val is None:
        return None
    val = val.strip()
    return val if val != "" else None


def to_int(val):
    val = clean(val)
    return int(val) if val is not None else None


def to_float(val):
    val = clean(val)
    return float(val) if val is not None else None


conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

with open("static/import/gear_import.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute(
            """
            INSERT INTO studio_gear (
                name_model, brand, format, hp, purchase_source, seller_listing,
                functions, quantity, rig, value, purchase_price, year_built, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean(row.get("name_model")),
                clean(row.get("brand")),
                clean(row.get("format")),
                to_int(row.get("hp")),
                clean(row.get("purchase_source")),
                clean(row.get("seller_listing")),
                clean(row.get("functions")),
                to_int(row.get("quantity")) or 1,
                clean(row.get("rig")),
                to_float(row.get("value")),
                to_float(row.get("purchase_price")),
                to_int(row.get("year_built")),
                clean(row.get("notes")),
            ),
        )

conn.commit()
conn.close()

print("✅ Gear import complete.")
