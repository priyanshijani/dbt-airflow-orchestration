"""Store database (OLTP) generator: products, customers, orders, order_items, refunds.

Every table is produced as a *version history* (`valid_from` column). The release step
(generators/release.py) writes the latest version as of the simulated clock into Postgres,
so status changes show up as `updated_at` moves: exactly what incremental extraction needs.
"""
import re
from datetime import datetime, time, timedelta, timezone

import numpy as np
import pandas as pd
from faker import Faker

from generators import config

COUNTRY_CODES = {
    "United States": "US", "United Kingdom": "GB", "Canada": "CA", "India": "IN", "Germany": "DE",
    "France": "FR", "Spain": "ES", "Italy": "IT", "Netherlands": "NL", "Australia": "AU",
    "Japan": "JP", "Singapore": "SG", "Taiwan": "TW", "Brazil": "BR", "Mexico": "MX",
    "Ireland": "IE", "Sweden": "SE", "Poland": "PL", "Turkey": "TR", "South Korea": "KR",
}

# Backend first-party UTM capture. Campaign slugs match the ad exports via seeds/channel_mapping.
GOOGLE_CAMPAIGNS = (["brand_exact", "generic_apparel", "generic_drinkware", "shopping_all"], [.40, .25, .15, .20])
META_CAMPAIGNS = (["prospecting_broad", "prospecting_lal2", "retargeting_dpa", "uk_prospecting", "eu_prospecting"],
                  [.30, .20, .30, .10, .10])
UNTRACKED_MIX = {"paid_social": .35, "email": .15, "direct": .30, "paid_search": .10, "organic": .10}

STATUS_FLOW = ["placed", "paid", "shipped", "delivered"]


def _debrand(name: str, category: str | None) -> str:
    out = name or ""
    for word in config.BRAND_WORDS:
        out = re.sub(rf"\b{word}\b", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out).strip(" -|")
    return out or f"{category or 'Kestrel'} Item"


def _ts(d, rng: np.random.Generator) -> datetime:
    """Random timestamp on date d, weighted towards daytime US hours."""
    hour = int(np.clip(rng.normal(15, 4), 0, 23))
    return datetime.combine(d, time(hour, int(rng.integers(60)), int(rng.integers(60))), tzinfo=timezone.utc)


# ── products ────────────────────────────────────────────────────────────────

def build_products(items: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for n, r in enumerate(items.sort_values("item_id").itertuples(), start=1):
        price = round(float(r.price_usd), 2)
        created = datetime.combine(config.WINDOW_START - timedelta(days=int(rng.integers(30, 400))),
                                   time(9), tzinfo=timezone.utc)
        base = dict(product_id=r.item_id, sku=f"KG-{n:05d}", name=_debrand(r.item_name, r.item_category),
                    category=r.item_category or "Uncategorized", price_usd=price,
                    cost_usd=round(price * rng.uniform(.35, .55), 2), is_active=True, created_at=created)
        rows.append(dict(base, valid_from=created))
        if rng.random() < .08:  # mid-window price change → feeds the SCD2 snapshot in dbt
            change = config.WINDOW_START + timedelta(days=int(rng.integers(10, 80)))
            factor = rng.choice([.85, 1.10])
            rows.append(dict(base, price_usd=round(price * factor, 2),
                             valid_from=datetime.combine(change, time(6), tzinfo=timezone.utc)))
    return pd.DataFrame(rows)


def price_on(products: pd.DataFrame, product_id: str, at: datetime) -> float:
    versions = products[(products.product_id == product_id) & (products.valid_from <= at)]
    if versions.empty:
        versions = products[products.product_id == product_id]
    return float(versions.sort_values("valid_from").iloc[-1].price_usd)


# ── customers ───────────────────────────────────────────────────────────────

class CustomerFactory:
    def __init__(self, rng: np.random.Generator, seed: int):
        self.rng = rng
        self.fake = Faker("en_US")
        self.fake.seed_instance(seed)
        self.rows: list[dict] = []

    def new(self, created_at: datetime, country: str | None = None, region=None, city=None,
            accepts_marketing_p: float = .55) -> int:
        customer_id = 100_000 + len(self.rows) + 1
        first, last = self.fake.first_name(), self.fake.last_name()
        email = f"{first}.{last}{customer_id % 997}@{self.fake.safe_domain_name()}".lower()
        if self.rng.random() < .10:  # realistic mess: case + whitespace (staging normalises)
            email = f" {email.title()} "
        self.rows.append(dict(
            customer_id=customer_id, email=email, first_name=first, last_name=last,
            phone=self.fake.numerify("+1-###-###-####") if self.rng.random() < .6 else None,
            country_code=COUNTRY_CODES.get(country or "United States"),
            region=region if region not in (None, "(not set)") else None,
            city=city if city not in (None, "(not set)") else None,
            accepts_marketing=bool(self.rng.random() < accepts_marketing_p),
            created_at=created_at, valid_from=created_at,
        ))
        return customer_id

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


# ── orders ──────────────────────────────────────────────────────────────────

def _channel_from_ga4(source: str | None, medium: str | None, rng) -> tuple[str, str | None, str | None, str | None]:
    """(channel, utm_source, utm_medium, utm_campaign) as the backend would capture it."""
    source, medium = (source or "").lower(), (medium or "").lower()
    if medium == "cpc":
        return "paid_search", "google", "cpc", rng.choice(GOOGLE_CAMPAIGNS[0], p=GOOGLE_CAMPAIGNS[1])
    if source in ("<other>", "(data deleted)") and rng.random() < .45:
        return "paid_social", "facebook", "paid_social", rng.choice(META_CAMPAIGNS[0], p=META_CAMPAIGNS[1])
    if medium == "organic":
        return "organic", None, None, None
    if medium == "referral":
        return "referral", None, None, None
    return "direct", None, None, None


def _utm_for(channel: str, rng, campaign: str | None = None):
    if channel == "paid_social":
        return "facebook", "paid_social", campaign or rng.choice(META_CAMPAIGNS[0], p=META_CAMPAIGNS[1])
    if channel == "paid_search":
        return "google", "cpc", campaign or rng.choice(GOOGLE_CAMPAIGNS[0], p=GOOGLE_CAMPAIGNS[1])
    if channel == "email":
        return "newsletter", "email", campaign or "weekly_newsletter"
    return None, None, None


def build_orders(purchases: pd.DataFrame, products: pd.DataFrame, rng: np.random.Generator,
                 seed: int, email_campaigns: list[dict]) -> dict[str, pd.DataFrame]:
    customers = CustomerFactory(rng, seed)

    # Pre-window customer base: account holders / newsletter subscribers who may come back.
    for _ in range(int(1500 * config.SCALE)):
        created = datetime.combine(config.WINDOW_START - timedelta(days=int(rng.integers(20, 660))),
                                   time(int(rng.integers(24))), tzinfo=timezone.utc)
        customers.new(created, accepts_marketing_p=.70)

    popularity = (pd.Series([i["item_id"] for items in purchases["items"] for i in items])
                  .value_counts(normalize=True))
    popularity = popularity[popularity.index.isin(products.product_id)]
    popularity = popularity / popularity.sum()  # filtering drops mass; rng.choice needs weights summing to 1

    drafts: list[dict] = []   # one per order, before ids/status are assigned
    ga_user_to_customer: dict[str, int] = {}
    sellable = set(products.product_id)

    # 1) Tracked orders: one per GA4 purchase event
    for p in purchases.itertuples():
        if p.user_pseudo_id not in ga_user_to_customer:
            ga_user_to_customer[p.user_pseudo_id] = customers.new(
                p.event_ts.to_pydatetime() - timedelta(minutes=int(rng.integers(2, 30))),
                p.country, p.region, p.city)
        channel, src, med, camp = _channel_from_ga4(p.source, p.medium, rng)
        items = [(i["item_id"], max(int(i.get("quantity") or 1), 1)) for i in p.items
                 if i["item_id"] in sellable]
        if not items:
            continue
        drafts.append(dict(ts=p.event_ts.to_pydatetime(), customer_id=ga_user_to_customer[p.user_pseudo_id],
                           ga_session_id=int(p.ga_session_id) if pd.notna(p.ga_session_id) else None,
                           ga_client_id=p.user_pseudo_id, channel=channel, utm_source=src, utm_medium=med,
                           utm_campaign=camp, device_type=p.device_category, items=items))

    # 2) Untracked orders: real revenue GA4 never sees (consent / blockers / iOS)
    n_untracked = int(len(drafts) * config.UNTRACKED_ORDER_SHARE / (1 - config.UNTRACKED_ORDER_SHARE))
    tracked_dates = [d["ts"].date() for d in drafts]
    for _ in range(n_untracked):
        d = tracked_dates[int(rng.integers(len(tracked_dates)))]
        channel = rng.choice(list(UNTRACKED_MIX), p=list(UNTRACKED_MIX.values()))
        if channel == "paid_social" and config.in_range(d, config.META_CPM_SPIKE) and rng.random() < .30:
            continue  # story: CPM spike → fewer Meta-driven orders
        drafts.append(_untracked_draft(d, channel, customers, popularity, rng))

    # 3) Story: "last shipping day" email pulls returning customers back (Dec 15–17)
    for c in email_campaigns:
        if c["send_at"].date() == config.LAST_SHIPPING_EMAIL:
            for _ in range(int(140 * config.SCALE)):
                d = config.LAST_SHIPPING_EMAIL + timedelta(days=int(rng.choice([0, 0, 1, 2])))
                drafts.append(_untracked_draft(d, "email", customers, popularity, rng,
                                               campaign=c["slug"], returning=True))

    drafts.sort(key=lambda x: x["ts"])
    return _materialise(drafts, customers.frame(), products, rng)


def _untracked_draft(d, channel, customers: CustomerFactory, popularity: pd.Series, rng,
                     campaign: str | None = None, returning: bool | None = None) -> dict:
    ts = _ts(d, rng)
    existing = [c for c in customers.rows if c["created_at"] < ts]
    if returning is None:
        returning = rng.random() < .45
    pool = [c for c in existing if c["accepts_marketing"]] if channel == "email" else existing
    if returning and pool:
        customer_id = pool[int(rng.integers(len(pool)))]["customer_id"]
    else:
        customer_id = customers.new(ts - timedelta(minutes=int(rng.integers(2, 30))))
    n_items = int(rng.choice([1, 1, 2, 3]))
    picks = rng.choice(popularity.index, size=n_items, replace=False, p=popularity.values)
    src, med, camp = _utm_for(channel, rng, campaign)
    return dict(ts=ts, customer_id=customer_id, ga_session_id=None, ga_client_id=None, channel=channel,
                utm_source=src, utm_medium=med, utm_campaign=camp,
                device_type=rng.choice(["mobile", "desktop", "tablet"], p=[.6, .37, .03]),
                items=[(pid, int(rng.choice([1, 1, 1, 2]))) for pid in picks])


def _materialise(drafts, customers_df, products, rng) -> dict[str, pd.DataFrame]:
    order_versions, items_rows, refunds_rows = [], [], []
    first_order_seen: set[int] = set()
    item_id = 1
    for n, d in enumerate(drafts, start=1):
        order_id, ts, day = 500_000 + n, d["ts"], d["ts"].date()
        lines = [(pid, qty, price_on(products, pid, ts)) for pid, qty in d["items"]]
        subtotal = round(sum(q * p for _, q, p in lines), 2)

        discount_code, rate = None, 0.0
        if config.in_range(day, config.PROMO_WINDOW) and rng.random() < .65:
            discount_code, rate = "BFCM20", .20       # story: promo lifts AOV via bundles, cuts margin
        elif d["customer_id"] not in first_order_seen and rng.random() < .10:
            discount_code, rate = "WELCOME10", .10
        first_order_seen.add(d["customer_id"])
        discount = round(subtotal * rate, 2)
        shipping = 0.0 if subtotal - discount >= 75 else 7.95
        tax = round((subtotal - discount) * .075, 2)
        total = round(subtotal - discount + shipping + tax, 2)

        base = dict(order_id=order_id, order_number=f"KG{100000 + n}", customer_id=d["customer_id"],
                    ga_session_id=d["ga_session_id"], ga_client_id=d["ga_client_id"], currency="USD",
                    subtotal_usd=subtotal, discount_usd=discount, shipping_usd=shipping, tax_usd=tax,
                    total_usd=total, discount_code=discount_code, utm_source=d["utm_source"],
                    utm_medium=d["utm_medium"], utm_campaign=d["utm_campaign"], device_type=d["device_type"],
                    created_at=ts)

        # status lifecycle → multiple versions with increasing valid_from
        t = ts
        order_versions.append(dict(base, status="placed", valid_from=t))
        t += timedelta(minutes=int(rng.integers(1, 4)))
        if config.in_range(day, config.PAYMENT_OUTAGE) and rng.random() < config.PAYMENT_OUTAGE_FAIL_RATE:
            order_versions.append(dict(base, status="payment_failed", valid_from=t))  # story: payment outage
        else:
            order_versions.append(dict(base, status="paid", valid_from=t))
            if rng.random() < .025:
                order_versions.append(dict(base, status="cancelled",
                                           valid_from=t + timedelta(hours=int(rng.integers(1, 20)))))
            else:
                t += timedelta(hours=int(rng.integers(20, 72)))
                order_versions.append(dict(base, status="shipped", valid_from=t))
                t += timedelta(hours=int(rng.integers(48, 168)))
                order_versions.append(dict(base, status="delivered", valid_from=t))
                if rng.random() < .06:
                    full = rng.random() < .4
                    amount = total if full else round(lines[0][1] * lines[0][2] * (1 - rate), 2)
                    rt = t + timedelta(days=int(rng.integers(2, 20)))
                    refunds_rows.append(dict(refund_id=900_000 + len(refunds_rows) + 1, order_id=order_id,
                                             amount_usd=amount, reason=rng.choice(
                                                 ["damaged", "wrong_size", "not_as_described", "changed_mind"]),
                                             created_at=rt, valid_from=rt))

        for pid, qty, price in lines:
            items_rows.append(dict(order_item_id=item_id, order_id=order_id, product_id=pid, quantity=qty,
                                   unit_price_usd=price, line_discount_usd=round(qty * price * rate, 2),
                                   created_at=ts, valid_from=ts))
            item_id += 1

    orders = pd.DataFrame(order_versions)
    channels = pd.DataFrame([{"order_id": 500_000 + n, "channel": d["channel"]} for n, d in enumerate(drafts, 1)])
    return {
        "customers": customers_df,
        "orders": orders,
        "order_items": pd.DataFrame(items_rows),
        "refunds": pd.DataFrame(refunds_rows),
        "_order_channels": channels,  # generator-internal: used by ads/budget, never loaded
    }
