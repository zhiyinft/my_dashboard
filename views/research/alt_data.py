import streamlit as st

from core import analytics as an
from core import charts
from core.data import load
from core.datasets import ALT_METRICS
from core.ui import SIGNAL_STYLE, chart, gain_loss, grid, header, kpis, section, table_height

header("Alternative Data", "Card spend, app users and web traffic as YoY growth, and whether growth is speeding up")

sig = an.alt_signals()
held = sig[sig["weight"] > 0]
slowing = held[held["signal"] == "Decelerating"]

kpis("alt", [
    {"label": "Names covered", "value": len(sig), "delta": f"{len(held)} in the book", "delta_color": "off", "delta_arrow": "off"},
    {"label": "Accelerating", "value": int((sig["signal"] == "Accelerating").sum())},
    {"label": "Decelerating", "value": int((sig["signal"] == "Decelerating").sum())},
    {"label": "Holdings slowing", "value": len(slowing), "delta": f"{slowing['weight'].sum():.1%} of NAV",
     "delta_color": "off", "delta_arrow": "off"},
])

if len(slowing):
    st.warning(
        "Decelerating holdings: " + ", ".join(f"**{t}** ({w:.1%} of NAV, {m * 100:+.1f} pp)"
                                              for t, w, m in zip(slowing.index, slowing["weight"], slowing["momentum"])),
        icon=":material/trending_down:",
    )

with grid("alt_overview", "wide"):
    with st.container():
        section("Signals", "Momentum: latest 4-week YoY minus the prior 13 weeks, averaged across metrics")
        arrows = {"Accelerating": "↑ Accelerating", "Stable": "→ Stable", "Decelerating": "↓ Decelerating"}
        table = sig[["name", "signal", "momentum", "weight"]].assign(
            signal=sig["signal"].map(arrows), momentum=sig["momentum"] * 100)
        st.dataframe(
            gain_loss(table, ["momentum"]),
            width="stretch",
            height=table_height(len(table)),
            column_config={
                "ticker": "Ticker",
                "name": "Name",
                "signal": "Signal",
                "momentum": st.column_config.NumberColumn("Momentum", format="%+.1f pp"),
                "weight": st.column_config.NumberColumn("Our weight", format="percent"),
            },
        )
    with st.container():
        section("Latest YoY by metric", "4-week average")
        chart(*charts.alt_heatmap(), key="alt_heat")

section("Drill-down")
default = slowing.index[0] if len(slowing) else sig.index[0]
ticker = st.selectbox("Ticker", list(sig.index), index=list(sig.index).index(default), width=320,
                      format_func=lambda t: f"{t} · {sig.at[t, 'name']}")
row = sig.loc[ticker]
icon, color = SIGNAL_STYLE[row["signal"]]
with st.container(horizontal=True, vertical_alignment="center"):
    st.badge(row["signal"], icon=icon, color=color)
    st.caption(f"In the book at {row['weight']:.1%}" if row["weight"] > 0 else "Not in the book")

data = load("alt_data").sort_values("week")
with grid("alt_metrics", "cards"):
    for metric in ALT_METRICS:
        s = data.query("ticker == @ticker and metric == @metric")["yoy"]
        if s.empty:
            continue
        latest, prior = s.iloc[-4:].mean(), s.iloc[-17:-4].mean()
        with st.container(border=True):
            st.metric(f"{metric}, YoY (4-week avg)", f"{latest:+.1%}", f"{(latest - prior) * 100:+.1f} pp vs prior 13 weeks")
            chart(*charts.alt_trend(ticker, metric), key=f"alt_{metric}")
