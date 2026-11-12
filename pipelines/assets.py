"""Airflow Assets: one per raw source family. Ingestion tasks produce them; dbt_transform (Phase 3) consumes them.

An asset event is emitted only when a run actually loaded new rows (see dags/_util.py), so dbt does not rebuild
when nothing changed.
"""
from airflow.sdk import Asset

RAW_SHOP = Asset("clickhouse://raw/shop")
RAW_GA4 = Asset("clickhouse://raw/ga4")
RAW_META_ADS = Asset("clickhouse://raw/meta_ads")
RAW_GOOGLE_ADS = Asset("clickhouse://raw/google_ads")
RAW_EMAIL = Asset("clickhouse://raw/email")
RAW_BUDGET = Asset("clickhouse://raw/budget")
RAW_HOLIDAYS = Asset("clickhouse://raw/holidays")
RAW_WEATHER = Asset("clickhouse://raw/weather")
RAW_FRED = Asset("clickhouse://raw/fred")
