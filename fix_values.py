import sqlite3
from config import DATABASE

conn = sqlite3.connect(DATABASE)
cur = conn.cursor()

cur.execute("""
    UPDATE studio_gear
    SET value = purchase_price
    WHERE (value IS NULL OR trim(CAST(value AS TEXT)) = '')
      AND purchase_price IS NOT NULL
""")

conn.commit()
print(f"✅ Updated rows: {cur.rowcount}")
conn.close()

