"""Rendering helpers shared by every page."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import analytics as an
from core.data import source
from core.datasets import DATASETS
from core.theme import is_dark

CHART_CONFIG = {"displayModeBar": False}

# Rows of headline numbers and card grids become auto-fit grids: on narrow screens
# items wrap onto new rows at equal width instead of squeezing or stretching.
# Containers opt in by key prefix; "wide" pairs a 3:2 main/side split.
CSS = """
<style>
[data-testid='stSidebarHeader'] {height: auto;}
[data-testid='stSidebarLogo'] {height: 4rem;}
[class*='st-key-kpis_'], [class*='st-key-cards_'], [class*='st-key-grid_'] {display: grid !important;}
[class*='st-key-kpis_'] {grid-template-columns: repeat(auto-fit, minmax(8.25rem, 1fr));}
[class*='st-key-cards_'] {grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));}
[class*='st-key-grid_'] {grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr));}
[class*='st-key-kpis_'] > div, [class*='st-key-cards_'] > div, [class*='st-key-grid_'] > div {width: auto !important; min-width: 0;}
[data-testid='stMetricLabel'] *, [data-testid='stMetricDelta'] * {white-space: normal !important; overflow: visible !important;}
[data-testid='stMetricDelta'] {height: auto !important;}
[class*='st-key-wide_'] > div:first-child {flex: 3 1 30rem; min-width: min(100%, 30rem);}
[class*='st-key-wide_'] > div:last-child {flex: 2 1 20rem; min-width: min(100%, 20rem);}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(f"{subtitle} · As of {an.as_of():%a %d %b %Y} close")


def kpis(key: str, items: list[dict]) -> None:
    """A wrapping row of bordered st.metric cards; each item holds st.metric kwargs."""
    with st.container(horizontal=True, gap="small", key=f"kpis_{key}"):
        for item in items:
            st.metric(border=True, width="stretch", **item)


def grid(key: str, kind: str = "grid"):
    """Horizontal container whose children wrap. kind: grid (charts), cards (small cards), wide (3:2 pair)."""
    return st.container(horizontal=True, gap="medium", key=f"{kind}_{key}")


def chart(fig: go.Figure, data: pd.DataFrame | None = None, key: str | None = None) -> None:
    """Plotly chart plus a collapsed table view of the same numbers."""
    st.plotly_chart(fig, key=key, config=CHART_CONFIG)
    if data is not None:
        with st.expander("Data", icon=":material/table:"):
            st.dataframe(data, width="stretch")


def section(title: str, note: str | None = None) -> None:
    st.subheader(title)
    if note:
        st.caption(note)


def money(x: float, signed: bool = False) -> str:
    sign = "-" if x < 0 else ("+" if signed else "")
    x = abs(x)
    for unit, div in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if x >= div:
            return f"{sign}${x / div:,.2f}{unit}"
    return f"{sign}${x:,.0f}"


def gain_loss(df: pd.DataFrame, columns: list[str]):
    """Styler that colors positive values green and negative red in the given columns."""
    up, down = ("#0ca30c", "#e66767") if is_dark() else ("#006300", "#c42b2b")
    return df.style.map(lambda v: f"color: {up}" if v > 0 else (f"color: {down}" if v < 0 else ""),
                        subset=[c for c in columns if c in df])


def table_height(rows: int) -> int:
    return 35 * (rows + 1) + 3


ACTION_COLOR = {"Initiate": "blue", "Add": "blue", "Trim": "violet", "Exit": "violet"}

SIGNAL_STYLE = {
    "Accelerating": (":material/trending_up:", "green"),
    "Stable": (":material/trending_flat:", "gray"),
    "Decelerating": (":material/trending_down:", "red"),
}


def outcome_badge(worked: bool) -> None:
    if worked:
        st.badge("Worked", icon=":material/check:", color="green")
    else:
        st.badge("Didn't work", icon=":material/close:", color="red")


def data_badge() -> None:
    live = sum(source(n) == "live" for n in DATASETS)
    if live == 0:
        st.badge("Mock data", icon=":material/science:", color="orange")
    elif live == len(DATASETS):
        st.badge("Live data", icon=":material/check_circle:", color="green")
    else:
        st.badge(f"Partly live ({live}/{len(DATASETS)})", icon=":material/science:", color="orange")


def init_state() -> None:
    st.session_state.setdefault("suggestion_status", {sid: "pending" for sid in an.suggestions()["id"]})
    st.session_state.setdefault("deck", ["performance", "sectors", "contributors", "alt_heatmap", "pb_sectors"])
    st.session_state.setdefault("slide", 0)


def accepted_suggestions() -> pd.DataFrame:
    s = an.suggestions()
    status = st.session_state["suggestion_status"]
    return s[s["id"].map(status) == "accepted"]
