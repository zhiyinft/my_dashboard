from html import escape

import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts, config
from core.ui import chart, gain_loss, grid, header, kpis, section, table_height

header("Catalysts", "Upcoming events for our holdings, agent ideas, the watchlist and the market")

cal = an.catalysts()
today = an.today()
colors = charts.group_colors()
LABELS = {"Holding": "Holdings", "Agent idea": "Agent ideas", "Watchlist": "Watchlist", "Market": "Market"}
WINDOWS = {"Next 7 days": 7, "Next 30 days": 30, "Next 90 days": 90}

def when(days: int) -> str:
    return {0: "today", 1: "tomorrow"}.get(days, f"in {days} days")


held = cal[cal["group"] == "Holding"]
reporting = held[held["days"].between(0, 14) & (held["event_type"] == "Earnings")]
nxt = held[held["days"] >= 0].head(1)
kpis("cat", [
    {"label": "Holdings reporting, next 14 days", "value": len(reporting),
     "delta": f"{reporting['weight'].sum():.1%} of NAV", "delta_color": "off", "delta_arrow": "off"},
    {"label": "Events, next 7 days", "value": int(cal["days"].between(0, 7).sum())},
    {"label": "High importance, next 30 days", "value": int((cal["days"].between(0, 30) & (cal["importance"] == "High")).sum())},
    {"label": "Next holding event",
     "value": f"{nxt['ticker'].iloc[0]} · {nxt['date'].iloc[0]:%d %b}" if len(nxt) else "None",
     "delta": f"{nxt['event_type'].iloc[0]}, {when(nxt['days'].iloc[0])}" if len(nxt) else None,
     "delta_color": "off", "delta_arrow": "off"},
])

week = held[held["days"].between(0, config.ATTENTION_DAYS) & (held["importance"] == "High")]
if len(week):
    st.warning(
        f"**Next {config.ATTENTION_DAYS} days for the book:** " + "; ".join(
            f"{r.ticker} {r.title.lower() if r.event_type == 'Earnings' else r.title} {r.date:%a %d %b}"
            f"{', ' + r.timing.lower() if isinstance(r.timing, str) else ''} ({r.weight:.1%} of NAV)"
            for r in week.itertuples()),
        icon=":material/event_upcoming:",
    )

with st.container(horizontal=True, vertical_alignment="bottom"):
    window = st.segmented_control("Window", list(WINDOWS), default="Next 30 days", required=True)
    shown = st.pills("Show", list(LABELS.values()), selection_mode="multi", default=list(LABELS.values()))
    high_only = st.toggle("High importance only")

groups = [g for g, label in LABELS.items() if label in (shown or [])]


def keep(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["group"].isin(groups)
    if high_only:
        mask &= df["importance"] == "High"
    return df[mask]


def dot(group: str, earnings: bool) -> str:
    return f"<span style='color:{colors[group]}'>{'●' if earnings else '◆'}</span>"


st.markdown(
    " &nbsp; ".join(f"{dot(g, True)}&nbsp;{LABELS[g]}" for g in an.GROUPS)
    + " &nbsp;·&nbsp; ●&nbsp;earnings &nbsp; ◆&nbsp;other&nbsp;event",
    unsafe_allow_html=True,
)

section("Next five trading days")
with grid("days", "week"):
    for d in pd.bdate_range(today, periods=5):
        with st.container(border=True):
            st.markdown(f"**{d:%a %d %b}**" + (" · today" if d == today else ""))
            day = keep(cal[cal["date"] == d])
            if day.empty:
                st.caption("No events")
            for r in day.itertuples():
                who = escape(r.ticker if isinstance(r.ticker, str) else "Market")
                when = f" · {r.timing.lower()}" if isinstance(r.timing, str) else ""
                st.markdown(f"{dot(r.group, r.event_type == 'Earnings')} **{who}** {escape(r.title)}"
                            f"<br><span style='opacity:.65;font-size:.85em'>{escape(r.importance)}{when}</span>",
                            unsafe_allow_html=True)

days = WINDOWS[window]
upcoming = keep(cal[cal["days"].between(0, days)])
section(f"Timeline, {window.lower()}", "Market first, then holdings by weight, agent ideas and the watchlist")
if upcoming.empty:
    st.info("No events match these filters.", icon=":material/filter_alt_off:")
else:
    chart(*charts.catalyst_timeline(upcoming, today, today + pd.Timedelta(days=days)), key="cat_timeline")

    section("Calendar", f"{len(upcoming)} events, soonest first")
    table = upcoming.set_index("ticker")[
        ["date", "days", "event_type", "title", "timing", "importance", "status", "weight", "group", "note"]
    ].assign(importance=lambda x: x["importance"].astype(str), group=lambda x: x["group"].astype(str),
             timing=lambda x: x["timing"].fillna(""), note=lambda x: x["note"].fillna(""))
    table.index = table.index.fillna("Market")
    st.dataframe(
        table,
        width="stretch",
        height=table_height(len(table)),
        column_config={
            "ticker": st.column_config.TextColumn("Ticker", pinned=True),
            "date": st.column_config.DateColumn("Date", format="ddd D MMM"),
            "days": st.column_config.NumberColumn("In", format="%d days"),
            "event_type": "Type",
            "title": st.column_config.TextColumn("Event", width="medium"),
            "timing": "Timing",
            "importance": "Importance",
            "status": "Status",
            "weight": st.column_config.NumberColumn("Our weight", format="percent"),
            "group": "For",
            "note": st.column_config.TextColumn("What to watch", width="medium"),
        },
    )

recent = keep(cal[cal["days"].between(-14, -1) & cal["ticker"].notna()])
section("Recent events", "How the stock moved on the first session after the news, last 14 days")
if recent.empty:
    st.caption("No recent events match these filters.")
else:
    past = recent.set_index("ticker")[["date", "event_type", "title", "move", "excess", "weight"]]
    st.dataframe(
        gain_loss(past, ["move", "excess"]),
        width="stretch",
        height=table_height(len(past)),
        column_config={
            "ticker": st.column_config.TextColumn("Ticker", pinned=True),
            "date": st.column_config.DateColumn("Date", format="ddd D MMM"),
            "event_type": "Type",
            "title": "Event",
            "move": st.column_config.NumberColumn("Stock move", format="percent"),
            "excess": st.column_config.NumberColumn("vs benchmark", format="percent"),
            "weight": st.column_config.NumberColumn("Our weight", format="percent"),
        },
    )
