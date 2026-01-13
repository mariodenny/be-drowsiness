import os
import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "drowsiness_db"
}

SCHEMA_DIR = "./schemas"

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

sql_files = sorted([
    f for f in os.listdir(SCHEMA_DIR)
    if f.endswith(".sql")
])

for file in sql_files:
    path = os.path.join(SCHEMA_DIR, file)
    print(f"Executing {file} ...")

    with open(path, "r") as f:
        sql = f.read()

    try:
        for result in cursor.execute(sql, multi=True):
            pass
        conn.commit()
    except Exception as e:
        print(f"❌ Error in {file}")
        print(e)
        break

cursor.close()
conn.close()
print("✅ Done")
