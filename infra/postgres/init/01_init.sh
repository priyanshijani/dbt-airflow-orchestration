#!/bin/bash
# One Postgres instance, two databases (ADR-008):
#   airflow: Airflow metadata
#   shop:    the simulated production store database (an OLTP source)
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username postgres <<-SQL
  CREATE ROLE ${AIRFLOW_DB_USER} LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
  CREATE DATABASE airflow OWNER ${AIRFLOW_DB_USER};

  CREATE ROLE ${SHOP_DB_USER} LOGIN PASSWORD '${SHOP_DB_PASSWORD}';
  CREATE DATABASE shop OWNER ${SHOP_DB_USER};
SQL

psql -v ON_ERROR_STOP=1 --username "${SHOP_DB_USER}" --dbname shop -f /docker-entrypoint-initdb.d/sql/shop_schema.sql
