"""Shared constants for the Kestrel Goods synthetic universe (05_DATA_STRATEGY, ADR-018)."""
import os
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[1]))
GA4_SAMPLE = ROOT / "data" / "samples" / "ga4" / "ga4_events.parquet"
OUT_DIR = ROOT / "data" / "generated"
SHOP_DIR = OUT_DIR / "shop"          # parquet snapshots of the OLTP tables (incl. order versions)
LANDING_DIR = OUT_DIR / "landing"    # files that get "delivered" to the S3 landing bucket

SEED = int(os.getenv("SEED", "42"))
SCALE = float(os.getenv("SCALE", "1"))

# GA4 public sample covers 2020-11-01..2021-01-31. Shifting by exactly 261 weeks keeps
# weekdays aligned AND lands Black Friday 2020 (Nov 27) on Black Friday 2025 (Nov 28).
GA4_SHIFT_DAYS = 261 * 7
WINDOW_START = date(2025, 11, 2)
WINDOW_END = date(2026, 2, 1)
# The last 14 days are held back and "released" one day at a time by the simulator (ADR-019).
INITIAL_RELEASE_THROUGH = WINDOW_END - timedelta(days=14)

# Planted stories: ground truth the Insight Narrator should rediscover (generators/STORIES.md)
BLACK_FRIDAY = date(2025, 11, 28)
CYBER_MONDAY = date(2025, 12, 1)
PROMO_WINDOW = (date(2025, 11, 24), date(2025, 12, 2))           # sitewide 20% code
META_CPM_SPIKE = (date(2025, 12, 8), date(2025, 12, 14))         # auction pressure on Meta
LAST_SHIPPING_EMAIL = date(2025, 12, 15)                         # email drives returning buyers
GOOGLE_SHOPPING_LAUNCH = (date(2026, 1, 12), date(2026, 1, 18))  # spend up, no session lift
PAYMENT_OUTAGE = (date(2026, 1, 20), date(2026, 1, 23))          # payment provider failures

UNTRACKED_ORDER_SHARE = 0.15   # orders with no GA4 session (consent declined / ad blockers)
PAYMENT_OUTAGE_FAIL_RATE = 0.35

BRAND_WORDS = ("Google", "YouTube", "Android", "Chrome", "Waze", "Noogler", "Gmail")


def window_days() -> list[date]:
    return [WINDOW_START + timedelta(days=i) for i in range((WINDOW_END - WINDOW_START).days + 1)]


def in_range(d: date, rng: tuple[date, date]) -> bool:
    return rng[0] <= d <= rng[1]
