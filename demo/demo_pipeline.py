import requests
import pandas as pd
import psycopg2
import time
import io

print("=" * 50)
print(" Demo Data Pipeline")
print(" Weather data load simulation")
print("=" * 50)

# Step 1: Download dataset
print("\n[1/3] Downloading weather dataset...")
url = "https://raw.githubusercontent.com/datasets/global-temp/master/data/annual.csv"
response = requests.get(url)
print(f"  Done. Size: {len(response.content)/1024:.1f} KB")

# Step 2: Parse + process
print("\n[2/3] Parsing and processing data...")
df = pd.read_csv(io.StringIO(response.text))
print(f"  Rows: {len(df)}")
print(f"  Columns: {list(df.columns)}")

for i in range(8):
    time.sleep(3)
    print(f"  Processing batch {i+1}/8...")

print("  Parsing complete.")

# Step 3: Load into Postgres
print("\n[3/3] Loading into Postgres...")
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="weatherdb",
    user="demo",
    password="demo123"
)
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS global_temp (
        id      SERIAL PRIMARY KEY,
        source  TEXT,
        year    INT,
        mean    FLOAT
    )
""")

rows = [(row.Source, row.Year, row.Mean) for _, row in df.iterrows()]

for i, row in enumerate(rows):
    cur.execute(
        "INSERT INTO global_temp (source, year, mean) VALUES (%s,%s,%s)",
        row
    )
    if i % 20 == 0:
        conn.commit()
        print(f"  Inserted {i}/{len(rows)} rows...")

conn.commit()
cur.close()
conn.close()

print(f"  Loaded {len(rows)} rows into Postgres.")
print("\n" + "=" * 50)
print(" Pipeline finished successfully")
print("=" * 50)
