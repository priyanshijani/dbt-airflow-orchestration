#!/bin/bash
# Databases, users and least-privilege grants (04_ARCHITECTURE §9, 06_GOVERNANCE §5).
# Runs once, on first start of an empty ClickHouse volume.
set -euo pipefail

clickhouse client --user "${CLICKHOUSE_USER}" --password "${CLICKHOUSE_PASSWORD}" --multiquery <<SQL
-- Warehouse layers (05_DATA_STRATEGY §6)
CREATE DATABASE IF NOT EXISTS raw;
CREATE DATABASE IF NOT EXISTS staging;
CREATE DATABASE IF NOT EXISTS intermediate;
CREATE DATABASE IF NOT EXISTS marts;
CREATE DATABASE IF NOT EXISTS meta;
CREATE DATABASE IF NOT EXISTS ai;

-- etl_writer: dlt + dbt. Owns every layer except ai.
CREATE USER IF NOT EXISTS etl_writer IDENTIFIED WITH sha256_password BY '${CLICKHOUSE_ETL_PASSWORD}';
GRANT ALL ON raw.*          TO etl_writer;
GRANT ALL ON staging.*      TO etl_writer;
GRANT ALL ON intermediate.* TO etl_writer;
GRANT ALL ON marts.*        TO etl_writer;
GRANT ALL ON meta.*         TO etl_writer;
GRANT CREATE TEMPORARY TABLE, S3, URL, FILE ON *.* TO etl_writer;
GRANT SELECT ON system.*    TO etl_writer;
-- dlt inspects existing tables through INFORMATION_SCHEMA before altering them
GRANT SELECT ON INFORMATION_SCHEMA.* TO etl_writer;
GRANT SELECT ON information_schema.* TO etl_writer;

-- agent_reader: AI agents. SELECT on governed marts only; limits enforced by profile.
CREATE USER IF NOT EXISTS agent_reader IDENTIFIED WITH sha256_password BY '${CLICKHOUSE_AGENT_PASSWORD}'
    SETTINGS PROFILE 'agent_readonly';
GRANT SELECT ON marts.* TO agent_reader;

-- hub_reader: Insights Hub. Marts + pipeline metadata + AI outputs.
CREATE USER IF NOT EXISTS hub_reader IDENTIFIED WITH sha256_password BY '${CLICKHOUSE_HUB_PASSWORD}'
    SETTINGS PROFILE 'hub_readonly';
GRANT SELECT ON marts.* TO hub_reader;
GRANT SELECT ON meta.*  TO hub_reader;
GRANT SELECT ON ai.*    TO hub_reader;

-- ai_writer: agents persist briefs, incidents and usage logs, nothing else.
CREATE USER IF NOT EXISTS ai_writer IDENTIFIED WITH sha256_password BY '${CLICKHOUSE_AI_WRITER_PASSWORD}';
GRANT SELECT, INSERT, CREATE TABLE ON ai.* TO ai_writer;
SQL

echo "ClickHouse databases, users and grants created."
