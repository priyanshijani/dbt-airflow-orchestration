"""Email platform export: campaign events as daily JSON-lines files (semi-structured source).

Deliberate mess (05_DATA_STRATEGY §4): nested `properties`, optional fields, local-time
timestamps with UTC offsets, Apple Mail machine opens inflating open rates.
"""
import json
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from generators import config

NY = ZoneInfo("America/New_York")

CAMPAIGNS = [  # (send date, slug, name, subject)
    ("2025-11-04", "weekly_newsletter", "Weekly newsletter #44", "New drops for cooler days"),
    ("2025-11-11", "weekly_newsletter", "Weekly newsletter #45", "Layer up: the fleece edit"),
    ("2025-11-18", "bfcm_early_access", "BFCM early access", "You're on the early-access list"),
    ("2025-11-25", "bfcm_teaser", "BFCM teaser", "20% off everything starts Friday"),
    ("2025-11-28", "black_friday_live", "Black Friday live", "It's here: 20% off sitewide"),
    ("2025-12-01", "cyber_monday", "Cyber Monday", "Last chance: BFCM ends tonight"),
    ("2025-12-04", "weekly_newsletter", "Weekly newsletter #48", "Gifts under $30"),
    ("2025-12-09", "gift_guide", "Holiday gift guide", "The 2025 gift guide"),
    ("2025-12-15", "last_shipping_day", "Last shipping day", "Order today for delivery by the 24th"),
    ("2025-12-19", "gift_cards", "Digital gift cards", "Too late to ship? Send a gift card"),
    ("2025-12-26", "boxing_day", "Boxing Day sale", "After-Christmas sale: up to 30% off"),
    ("2026-01-06", "new_year", "New year new gear", "Fresh start, fresh kit"),
    ("2026-01-13", "weekly_newsletter", "Weekly newsletter #02", "Bestsellers are back"),
    ("2026-01-20", "winter_clearance", "Winter clearance", "Clearance: final markdowns"),
    ("2026-01-27", "weekly_newsletter", "Weekly newsletter #04", "What's new this week"),
]


def campaigns() -> list[dict]:
    out = []
    for i, (d, slug, name, subject) in enumerate(CAMPAIGNS, start=1):
        send_local = datetime.combine(datetime.fromisoformat(d).date(), time(9, 30), tzinfo=NY)
        out.append(dict(campaign_id=f"cmp_{i:03d}", slug=slug, name=name, subject=subject,
                        send_at=send_local.astimezone(timezone.utc)))
    return out


def build_events(customers: pd.DataFrame, rng: np.random.Generator) -> tuple[list[dict], pd.DataFrame]:
    """Returns (events, unsubscribes[email, unsubscribed_at])."""
    prospects = [f"subscriber{i}@example.net" for i in range(int(800 * config.SCALE))]
    unsubscribed: dict[str, datetime] = {}
    events = []
    for c in campaigns():
        audience = customers[customers.accepts_marketing & (customers.created_at < c["send_at"])]
        recipients = [(r.email, int(r.customer_id)) for r in audience.itertuples()]
        recipients += [(e, None) for e in prospects]
        share = .9 if c["slug"] in ("black_friday_live", "last_shipping_day", "cyber_monday") else .5
        for email, customer_id in recipients:
            key = email.strip().lower()
            if key in unsubscribed or rng.random() > share:
                continue
            sent = c["send_at"] + timedelta(seconds=int(rng.integers(0, 900)))
            events.append(_event("email_sent", sent, email, customer_id, c))
            if rng.random() < .40:
                machine = bool(rng.random() < .45)  # Apple MPP auto-opens
                opened = sent + timedelta(minutes=1 if machine else int(rng.exponential(300)))
                events.append(_event("email_open", opened, email, customer_id, c, machine_open=machine))
                if not machine and rng.random() < (.12 if c["slug"] == "last_shipping_day" else .07):
                    clicked = opened + timedelta(seconds=int(rng.integers(5, 240)))
                    events.append(_event("email_click", clicked, email, customer_id, c,
                                         url=f"https://kestrelgoods.example/collections/{c['slug']}"))
            if rng.random() < .002:
                unsub = sent + timedelta(hours=int(rng.integers(1, 48)))
                unsubscribed[key] = unsub
                events.append(_event("email_unsubscribe", unsub, email, customer_id, c))
    unsubs = pd.DataFrame([{"email_key": k, "unsubscribed_at": v} for k, v in unsubscribed.items()])
    return events, unsubs


def _event(kind: str, ts: datetime, email: str, customer_id, c: dict, **extra) -> dict:
    props = {"campaign_id": c["campaign_id"], "campaign_name": c["name"], "subject": c["subject"],
             "utm_campaign": c["slug"]}
    props.update({k: v for k, v in extra.items() if v is not None})
    profile = {"email": email}
    if customer_id is not None:      # optional field: prospects have no shop account
        profile["external_id"] = str(customer_id)
    event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{kind}|{c['campaign_id']}|{ts.isoformat()}|{email}")  # deterministic
    return {"id": str(event_id), "type": kind,
            "timestamp": ts.astimezone(NY).isoformat(), "profile": profile, "properties": props}


def write_files(events: list[dict], out_dir: Path) -> list[dict]:
    """One JSONL file per event day, delivered the following morning. Returns manifest rows."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_day: dict = {}
    for e in events:
        by_day.setdefault(datetime.fromisoformat(e["timestamp"]).date(), []).append(e)
    manifest = []
    for day, rows in sorted(by_day.items()):
        if day > config.WINDOW_END:
            continue
        path = out_dir / f"email_events_{day.isoformat()}.jsonl"
        with path.open("w") as f:
            for e in sorted(rows, key=lambda r: r["timestamp"]):
                f.write(json.dumps(e) + "\n")
        manifest.append(dict(source="email", path=path, delivered_on=day + timedelta(days=1)))
    return manifest
