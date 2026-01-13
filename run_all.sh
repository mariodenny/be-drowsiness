#!/bin/bash

DB_HOST="localhost"
DB_USER="root"
DB_PASS=""
DB_NAME="drowsiness_db"
SCHEMA_DIR="./schemas"

# Edit di vps

echo "Running SQL schemas from $SCHEMA_DIR"

for file in $(ls $SCHEMA_DIR/*.sql | sort); do
  echo "Executing $file ..."
  mysql -h"$DB_HOST" -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$file"

  if [ $? -ne 0 ]; then
    echo "❌ Error executing $file"
    exit 1
  fi
done

echo "✅ All schemas executed successfully"
