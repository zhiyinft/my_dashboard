import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts, config
from core.ui import chart, gain_loss, grid, header, kpis, money, section, table_height

header("Live Portfolio", "Where the book stands today and what needs attention")

as_of = an.as_of()
PERIODS = {
    "1M": as_of - pd.DateOffset(months=1),
    "3M": as_of - pd.DateOffset(months=3),
    "YTD": pd.Timestamp(as_of.year, 1, 1),
    "1Y": as_of - pd.DateOffset(years=1),
    "Since inception": None,
}
period = st.segmented_control("Period", list(PERIODS), default="YTD", required=True, key="live_period",
                              label_visibility="collapsed")
base = an.period_base(PERIODS[period])
port_ret, bench_ret = an.period_returns(base)

h = an.holdings()
nav = an.nav()
nav_now = nav["nav"].iloc[-1]
day_pnl = h["day_pnl"].sum()

kpis("live", [
    {"label": "NAV", "value": money(nav_now)},
    {"label": "Today", "value": money(day_pnl, signed=True), "delta": f"{day_pnl / (nav_now - day_pnl):+.2%}"},
    {"label": f"Return, {period}", "value": f"{port_ret:+.1%}",
     "delta": f"{(port_ret - bench_ret) * 100:+.1f} pp vs bench"},
    {"label": "Cash", "value": f"{an.cash_weight():.1%}", "delta": money(nav["cash"].iloc[-1]),
     "delta_color": "off", "delta_arrow": "off"},
    {"label": "Positions", "value": len(h)},
    {"label": "Beta", "value": f"{(h['weight'] * h['beta']).sum():.2f}", "help": "Weighted average of position betas"},
])

# What needs attention: each card links to the page that explains it.
crowd = an.crowding()
crowded = crowd[crowd["held"] & crowd["crowded"]]
alt = an.alt_signals()
slowing = alt[(alt["weight"] > 0) & (alt["signal"] == "Decelerating")]
sugg = an.suggestions()
pending = sugg[sugg["id"].map(st.session_state["suggestion_status"]) == "pending"]
dec = an.decision_outcomes()
last_d = dec["decision_date"].max()
last = dec[dec["decision_date"] == last_d]

with grid("attention", "cards"):
    with st.container(border=True):
        st.markdown(f":orange[:material/warning:] **{len(crowded)} crowded longs** · {crowded['weight'].sum():.1%} of NAV")
        st.caption(f"{', '.join(crowded.index)} at or above the {config.CROWDED_PCT}th percentile of hedge-fund exposure"
                   if len(crowded) else "No holding is crowded")
        st.page_link("views/research/pb_positioning.py", label="PB positioning", icon=":material/arrow_forward:")
    with st.container(border=True):
        st.markdown(f":orange[:material/trending_down:] **{len(slowing)} holdings slowing** in alt data")
        st.caption(", ".join(f"{t} ({w:.1%})" for t, w in slowing["weight"].items()) or "No holding is decelerating")
        st.page_link("views/research/alt_data.py", label="Alternative data", icon=":material/arrow_forward:")
    with st.container(border=True):
        st.markdown(f":blue[:material/smart_toy:] **{len(pending)} agent ideas** to review")
        top = pending.iloc[0] if len(pending) else None
        st.caption(f"Top: {top['action']} {top['ticker']} to {top['target_weight']:.1%} ({top['confidence']:.0%} confidence)"
                   if top is not None else "Nothing pending")
        st.page_link("views/portfolio/agent_suggestions.py", label="Agent suggestions", icon=":material/arrow_forward:")
    with st.container(border=True):
        st.markdown(f":blue[:material/event:] **Last decision {last_d:%d %b}** · {len(last)} trades")
        st.caption(f"{', '.join(f'{a} {t}' for a, t in zip(last['action'], last['ticker']))} · "
                   f"{last['worked'].mean():.0%} working so far")
        st.page_link("views/portfolio/decision_date.py", label="Decision date", icon=":material/arrow_forward:")

with grid("perf", "wide"):
    with st.container():
        section(f"Performance, {period}", f"Portfolio against {config.BENCHMARK_NAME.lower()}, cumulative")
        chart(*charts.performance(base), key="live_perf")
    with st.container():
        section("Today's movers", "Largest P&L moves at the last close")
        chart(*charts.day_movers(), key="live_movers")

with grid("bets"):
    with st.container():
        section("Sector bets", "Portfolio minus benchmark weight, percentage points")
        chart(*charts.active_sectors(), key="live_sectors")
    with st.container():
        section(f"Contributors & detractors, {period}", "Contribution to portfolio return, basis points")
        chart(*charts.contributors(base + pd.offsets.BDay(1)), key="live_contrib")

section("Holdings", f"{len(h)} positions, largest first")
cols = ["name", "weight", "day_change", "day_pnl", "total_return", "total_pnl", "market_value", "last", "sector", "trend_3m"]
table = h[[c for c in cols if c in h]].assign(day_pnl=h["day_pnl"] / 1e3, market_value=h["market_value"] / 1e6)
if "total_pnl" in table:
    table["total_pnl"] = table["total_pnl"] / 1e6
st.dataframe(
    gain_loss(table, ["day_change", "day_pnl", "total_return", "total_pnl"]),
    width="stretch",
    height=table_height(len(table)),
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", pinned=True),
        "name": "Name",
        "sector": "Sector",
        "weight": st.column_config.ProgressColumn("Weight", format="percent", min_value=0,
                                                  max_value=config.LIMITS["max_position"]),
        "last": st.column_config.NumberColumn("Last", format="dollar"),
        "day_change": st.column_config.NumberColumn("Day", format="percent"),
        "day_pnl": st.column_config.NumberColumn("Day P&L $K", format="%+.1f"),
        "total_return": st.column_config.NumberColumn("Since entry", format="percent", help="Return against average cost"),
        "total_pnl": st.column_config.NumberColumn("P&L $M", format="%+.2f", help="Unrealised P&L against average cost"),
        "market_value": st.column_config.NumberColumn("Value $M", format="%.2f"),
        "trend_3m": st.column_config.LineChartColumn("3 months"),
    },
)
