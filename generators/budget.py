"""Finance's budget & revenue-target workbook (spreadsheet source).

Deliberate mess: a title row, merged month headers, finance-style channel names that don't
match the ad exports, a notes column, and a mid-window revised version (v2) that replaces v1.
"""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from generators import config

MONTHS = [date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)]
FINANCE_CHANNELS = {  # finance label → generator channel(s)
    "Paid Social (FB/IG)": ["paid_social"],
    "Paid Search - Google": ["paid_search"],
    "Email / CRM": ["email"],
    "Organic, Direct & Referral": ["organic", "direct", "referral"],
}
BUDGET_USD = {"Paid Social (FB/IG)": [18000, 21000, 14000, 13000],
              "Paid Search - Google": [9000, 11000, 8000, 8000],
              "Email / CRM": [1200, 1200, 1200, 1200],
              "Organic, Direct & Referral": [0, 0, 0, 0]}


def build(orders: pd.DataFrame, order_channels: pd.DataFrame, rng: np.random.Generator,
          out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    first = orders.sort_values("valid_from").drop_duplicates("order_id").merge(order_channels, on="order_id")
    first["month"] = first.created_at.map(lambda t: date(t.year, t.month, 1))
    actual = first.groupby(["month", "channel"]).total_usd.sum()

    def target(label: str, m: date, uplift: float) -> int:
        rev = sum(actual.get((m, ch), 0.0) for ch in FINANCE_CHANNELS[label])
        if m == date(2026, 2, 1):  # Feb barely in window: plan from January
            rev = sum(actual.get((date(2026, 1, 1), ch), 0.0) for ch in FINANCE_CHANNELS[label]) * .9
        return int(round(rev * uplift * rng.uniform(.97, 1.08), -2))

    v1 = out_dir / "budget_plan_FY25Q4_v1.xlsx"
    _write(v1, "FY25 Q4 – FY26 Q1 Marketing Plan (v1)", lambda lbl, m: target(lbl, m, 1.08))
    v2 = out_dir / "budget_plan_FY25Q4_v2.xlsx"
    # v2: finance revises Jan/Feb targets down after a soft December close
    _write(v2, "FY25 Q4 – FY26 Q1 Marketing Plan (v2 – Jan reforecast)",
           lambda lbl, m: target(lbl, m, .98 if m.month in (1, 2) else 1.08))
    return [dict(source="budget", path=v1, delivered_on=date(2025, 10, 27)),
            dict(source="budget", path=v2, delivered_on=date(2026, 1, 5))]


def _write(path: Path, title: str, target_fn) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan"
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=2 + 2 * len(MONTHS))

    ws.cell(row=3, column=1, value="Channel")
    for i, m in enumerate(MONTHS):
        col = 2 + 2 * i
        ws.cell(row=3, column=col, value=m.strftime("%b %Y")).alignment = Alignment(horizontal="center")
        ws.merge_cells(start_row=3, start_column=col, end_row=3, end_column=col + 1)
        ws.cell(row=4, column=col, value="Budget ($)")
        ws.cell(row=4, column=col + 1, value="Revenue target ($)")
    ws.cell(row=3, column=2 + 2 * len(MONTHS), value="Notes")

    for r, label in enumerate(FINANCE_CHANNELS, start=5):
        ws.cell(row=r, column=1, value=label)
        for i, m in enumerate(MONTHS):
            ws.cell(row=r, column=2 + 2 * i, value=BUDGET_USD[label][i])
            ws.cell(row=r, column=3 + 2 * i, value=target_fn(label, m))
    ws.cell(row=5, column=2 + 2 * len(MONTHS), value="incl. BFCM boost in Nov")
    total_row = 5 + len(FINANCE_CHANNELS)
    ws.cell(row=total_row, column=1, value="Total").font = Font(bold=True)
    for c in range(2, 2 + 2 * len(MONTHS)):
        letter = ws.cell(row=4, column=c).column_letter
        ws.cell(row=total_row, column=c, value=f"=SUM({letter}5:{letter}{total_row - 1})")
    wb.save(path)
