"""Shared look for the Insights Hub: palette, page CSS, summary blocks, cards and the Plotly template (ADR-027).

The palette is one navy ramp. Navy marks the figures that matter and the icon discs on summary blocks; the lighter
steps tell channels apart in charts. Surfaces stay white on a pale blue-grey page.
"""
import base64
from html import escape

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY, BLUE, SKY, MIST, TINT = "#0B3A75", "#2F6DB5", "#7FA8DA", "#BBD3EE", "#E6EEF8"
PAGE, CARD = "#F3F6FA", "#FFFFFF"
TEXT, TEXT_2, MUTED = "#0F1E36", "#4B5565", "#6B7487"
LINE = "rgba(15, 30, 54, 0.08)"
POSITIVE, NEGATIVE, WARNING = "#15803d", "#dc2626", "#b45309"
FONT = "Figtree, system-ui, sans-serif"

# lucide icons (ISC licence), inner SVG only; drawn at 24x24 with a 1.75 stroke
ICONS = {
    "revenue": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/>'
            '<path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "receipt": '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/>'
               '<path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "megaphone": '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
             '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/>'
              '<path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "funnel": '<path d="M10 20a1 1 0 0 0 .55.9l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .52-1.34L21.74 4.67A1 1 0 0 0 21 3H3'
              'a1 1 0 0 0-.74 1.67l7.22 7.99A2 2 0 0 1 10 14z"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11"/>',
    "percent": '<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/>'
               '<circle cx="17.5" cy="17.5" r="2.5"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/>'
                '<path d="M3 10h18"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/>'
                '<path d="M3 12A9 3 0 0 0 21 12"/>',
    "layers": '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9'
              'a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/>'
              '<path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>'
             '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
}

CSS = f"""
<style>
.stApp {{ background: {PAGE}; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1440px; padding: 72px 32px 64px; }}
[data-testid="stSidebar"] {{ background: {CARD}; }}
.stApp, .stApp button, .stApp input {{ font-variant-numeric: tabular-nums; }}

.hub-header {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 8px 24px; margin-bottom: 8px; }}
.hub-header h1 {{ margin: 0; padding: 0; font-size: 28px; line-height: 36px; font-weight: 600; color: {TEXT}; }}
.hub-header p {{ margin: 4px 0 0; font-size: 15px; line-height: 22px; color: {TEXT_2}; }}
.hub-meta {{ display: inline-flex; align-items: center; gap: 8px; font-size: 13px; line-height: 20px;
  color: {TEXT_2}; background: {CARD}; border: 1px solid {LINE}; border-radius: 8px; padding: 6px 12px; }}
.hub-meta img {{ width: 16px; height: 16px; }}

.hub-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
.hub-kpi {{ display: flex; align-items: center; gap: 16px; padding: 20px; background: {CARD};
  border: 1px solid {LINE}; border-radius: 16px; box-shadow: 0 1px 2px rgba(15, 30, 54, 0.04); }}
.hub-disc {{ flex: none; display: grid; place-items: center; width: 48px; height: 48px; border-radius: 50%;
  background: {NAVY}; color: #fff; }}
.hub-disc img {{ width: 22px; height: 22px; }}
.hub-kpi__label {{ font-size: 14px; line-height: 20px; font-weight: 500; color: {TEXT_2}; }}
.hub-kpi__value {{ font-size: 28px; line-height: 36px; font-weight: 600; color: {NAVY}; }}
.hub-kpi__note {{ font-size: 13px; line-height: 20px; color: {MUTED}; }}
.hub-up {{ color: {POSITIVE}; font-weight: 500; }}
.hub-down {{ color: {NEGATIVE}; font-weight: 500; }}

.hub-strip {{ overflow: hidden; padding: 20px 0; background: {CARD}; border: 1px solid {LINE};
  border-radius: 16px; box-shadow: 0 1px 2px rgba(15, 30, 54, 0.04); }}
.hub-strip__grid {{ display: grid; grid-template-columns: repeat(3, 1fr); row-gap: 20px;
  margin-left: -1px; }}
.hub-strip__item {{ display: flex; align-items: center; gap: 12px; padding: 0 20px; border-left: 1px solid {LINE}; }}
.hub-strip .hub-disc {{ width: 40px; height: 40px; }}
.hub-strip .hub-disc img {{ width: 18px; height: 18px; }}
.hub-strip__label {{ font-size: 13px; line-height: 20px; font-weight: 500; color: {TEXT_2}; }}
.hub-strip__value {{ font-size: 20px; line-height: 28px; font-weight: 600; color: {TEXT}; }}
.hub-strip__note {{ font-size: 12px; line-height: 16px; color: {MUTED}; }}

[class*="st-key-card"] {{ padding: 20px 20px 12px; background: {CARD}; border: 1px solid {LINE};
  border-radius: 16px; box-shadow: 0 1px 2px rgba(15, 30, 54, 0.04); }}
.hub-card-title {{ font-size: 16px; line-height: 24px; font-weight: 600; color: {NAVY}; }}
.hub-card-sub {{ font-size: 13px; line-height: 20px; color: {MUTED}; }}
[data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
[data-baseweb="tag"] {{ background: {TINT} !important; color: {NAVY} !important; }}
[data-baseweb="tag"] svg {{ color: {NAVY}; }}

.hub-rank {{ display: grid; gap: 12px; padding: 4px 0 8px; }}
.hub-rank__row {{ display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; font-size: 14px; line-height: 20px; }}
.hub-rank__name {{ color: {TEXT}; }}
.hub-rank__value {{ color: {TEXT}; font-weight: 500; text-align: right; }}
.hub-rank__bar {{ grid-column: 1 / -1; height: 6px; border-radius: 3px; background: {TINT}; }}
.hub-rank__bar span {{ display: block; height: 100%; border-radius: 3px; background: {NAVY}; }}

.hub-legend {{ display: grid; gap: 10px; padding-top: 8px; font-size: 14px; line-height: 20px; }}
.hub-legend__row {{ display: grid; grid-template-columns: 12px 1fr auto; align-items: center; gap: 10px;
  color: {TEXT}; }}
.hub-legend__dot {{ width: 12px; height: 12px; border-radius: 3px; }}
.hub-legend__value {{ color: {TEXT_2}; }}

.hub-notice {{ display: flex; align-items: flex-start; gap: 10px; padding: 12px 16px; border-radius: 12px;
  font-size: 14px; line-height: 20px; }}
.hub-notice img {{ flex: none; width: 18px; height: 18px; margin-top: 1px; }}
.hub-notice--info {{ background: {TINT}; color: {NAVY}; }}
.hub-notice--ok {{ background: #e8f4ec; color: #166534; }}
.hub-notice--warn {{ background: #fdf3e3; color: #92400e; }}
.hub-notice--error {{ background: #fdecec; color: #991b1b; }}

@media (max-width: 960px) {{ .hub-strip__grid {{ grid-template-columns: repeat(2, 1fr); }} }}
@media (max-width: 640px) {{
  .hub-strip__grid {{ grid-template-columns: 1fr; }}
  [data-testid="stMainBlockContainer"] {{ padding: 64px 16px 48px; }}
  .hub-kpi__value {{ font-size: 24px; line-height: 32px; }}
}}
</style>
"""

pio.templates["hub"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=12, color=TEXT_2),
    paper_bgcolor=CARD, plot_bgcolor=CARD,  # charts always sit on a white card
    colorway=[NAVY, BLUE, SKY, MIST],
    xaxis=dict(showgrid=False, zeroline=False, linecolor="rgba(15,30,54,0.16)", ticks="",
               tickfont=dict(color=MUTED), automargin=True),
    yaxis=dict(gridcolor="rgba(15,30,54,0.06)", zeroline=False, ticks="", tickfont=dict(color=MUTED),
               automargin=True),
    legend=dict(font=dict(color=TEXT_2), orientation="h", y=-0.15, x=0),
    hoverlabel=dict(bgcolor=CARD, bordercolor="rgba(15,30,54,0.16)", font=dict(family=FONT, color=TEXT)),
    margin=dict(t=8, b=8, l=8, r=8),
))
pio.templates.default = "hub"


def icon(name: str, colour: str = "#ffffff") -> str:
    """An <img> with the icon as a data URI: st.html sanitises inline <svg> away, images survive."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="' + colour + '" '
           'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">' + ICONS[name] + '</svg>')
    return f'<img alt="" src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">'


def setup(page_title: str) -> None:
    """Page config plus the shared CSS. Call first on every page."""
    st.set_page_config(page_title=page_title, layout="wide")
    st.html(CSS)


def header(title: str, subtitle: str = "", meta: str = "") -> None:
    side = f'<div class="hub-meta">{icon("calendar", NAVY)}{escape(meta)}</div>' if meta else ""
    sub = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    st.html(f'<div class="hub-header"><div><h1>{escape(title)}</h1>{sub}</div>{side}</div>')


def change(now: float, before: float | None, label: str, lower_is_better: bool | None = False) -> str:
    """'+4.2% vs <label>', coloured by whether the move is good (None: no colour, e.g. spend).

    Empty when there is nothing to compare."""
    if not before:
        return ""
    now, before = float(now), float(before)  # ClickHouse counts arrive as uint64, which wrap on subtraction
    ratio = (now - before) / before
    good = (ratio < 0) if lower_is_better else (ratio > 0)
    cls = "" if lower_is_better is None or not ratio else "hub-up" if good else "hub-down"
    return f'<span class="{cls}">{ratio:+.1%}</span> vs {escape(label)}'


def kpis(items: list[dict]) -> None:
    """Summary blocks: each item has label, value, icon and an optional note (HTML, from change() or escaped)."""
    cards = "".join(
        f'<div class="hub-kpi" title="{escape(i.get("help", ""))}"><div class="hub-disc">{icon(i["icon"])}</div>'
        f'<div><div class="hub-kpi__label">{escape(i["label"])}</div>'
        f'<div class="hub-kpi__value">{escape(i["value"])}</div>'
        f'<div class="hub-kpi__note">{i.get("note") or "&nbsp;"}</div></div></div>'
        for i in items
    )
    st.html(f'<div class="hub-kpis">{cards}</div>')


def strip(items: list[dict]) -> None:
    """The secondary figures, side by side in one card with hairline dividers."""
    cells = "".join(
        f'<div class="hub-strip__item"><div class="hub-disc">{icon(i["icon"])}</div><div>'
        f'<div class="hub-strip__label">{escape(i["label"])}</div>'
        f'<div class="hub-strip__value">{escape(i["value"])}</div>'
        f'<div class="hub-strip__note">{escape(i.get("note", ""))}</div></div></div>'
        for i in items
    )
    st.html(f'<div class="hub-strip"><div class="hub-strip__grid">{cells}</div></div>')


def card(key: str, title: str, subtitle: str = ""):
    """A white card with a title; use as a context manager. key must be unique on the page."""
    box = st.container(key=f"card_{key}")
    sub = f'<div class="hub-card-sub">{escape(subtitle)}</div>' if subtitle else ""
    box.html(f'<div class="hub-card-title">{escape(title)}</div>{sub}')
    return box


def ranked(rows: list[tuple[str, float]], fmt) -> None:
    """A ranked list with thin bars, for a top-n next to a bigger chart."""
    top = max((v for _, v in rows), default=0) or 1
    body = "".join(
        f'<div class="hub-rank__row"><span class="hub-rank__name">{escape(name)}</span>'
        f'<span class="hub-rank__value">{escape(fmt(value))}</span>'
        f'<div class="hub-rank__bar"><span style="width:{value / top:.1%}"></span></div></div>'
        for name, value in rows
    )
    st.html(f'<div class="hub-rank">{body}</div>')


def legend(rows: list[tuple[str, str, str]]) -> None:
    """(colour, label, value) rows, for a donut whose own legend cannot show values."""
    body = "".join(
        f'<div class="hub-legend__row"><span class="hub-legend__dot" style="background:{c}"></span>'
        f'<span>{escape(label)}</span><span class="hub-legend__value">{escape(value)}</span></div>'
        for c, label, value in rows
    )
    st.html(f'<div class="hub-legend">{body}</div>')


def notice(text: str, tone: str = "info") -> None:
    """A quiet status line. text may hold <b> tags; escape anything that comes from data."""
    name, colour = {"info": ("info", NAVY), "ok": ("check", "#166534"), "warn": ("alert", "#92400e"),
                    "error": ("x", "#991b1b")}[tone]
    st.html(f'<div class="hub-notice hub-notice--{tone}">{icon(name, colour)}<div>{text}</div></div>')


def chart(fig: go.Figure) -> None:
    # explicit: Streamlit swaps the process-wide Plotly default and fills unset backgrounds from its own theme
    fig.update_layout(template="hub", paper_bgcolor=CARD, plot_bgcolor=CARD)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def status_styler(df, column: str):
    """Colour a status column by state (labels from db.status_label) for st.dataframe."""
    colours = {"OK": POSITIVE, "Pass": POSITIVE, "Warning": WARNING, "Failed": NEGATIVE, "Error": NEGATIVE}

    def paint(v):
        c = colours.get(str(v), MUTED if str(v).startswith("Skipped") else None)
        return f"color: {c}; font-weight: 500" if c else ""

    return df.style.map(paint, subset=[column])
