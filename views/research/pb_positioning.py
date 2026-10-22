import streamlit as st

from core import analytics as an
from core import charts, config
from core.ui import chart, gain_loss, grid, header, kpis, section, table_height

header("Prime Broker Positioning", "Hedge-fund leverage, sector positioning and crowding, against our book")

lev = an.pb_leverage()
crowd = an.crowding()
sectors = an.pb_sectors()
crowded_held = crowd[crowd["held"] & crowd["crowded"]]
crowded_bets = sectors[(sectors["percentile_3y"] >= config.CROWDED_PCT - 5) & (sectors["active"] > 0.02)]

kpis("pb", [
    {"label": "Gross leverage", "value": f"{lev['gross'].iloc[-1]:.0%}",
     "delta": f"{(lev['gross'].iloc[-1] - lev['gross'].iloc[-2]) * 100:+.1f} pp WoW", "delta_color": "off"},
    {"label": "Net leverage", "value": f"{lev['net'].iloc[-1]:.0%}",
     "delta": f"{(lev['net'].iloc[-1] - lev['net'].iloc[-2]) * 100:+.1f} pp WoW", "delta_color": "off"},
    {"label": "Net leverage, 3y percentile", "value": f"{(lev['net'] < lev['net'].iloc[-1]).mean() * 100:.0f}th",
     "help": "Where today's net leverage sits in its 3-year range"},
    {"label": "Crowded longs we hold", "value": len(crowded_held), "delta": f"{crowded_held['weight'].sum():.1%} of NAV",
     "delta_color": "off", "delta_arrow": "off"},
])

if len(crowded_held):
    st.warning(
        f"**Crowded longs in the book:** {', '.join(f'{t} ({w:.1%})' for t, w in crowded_held['weight'].items())}. "
        f"All sit at or above the {config.CROWDED_PCT}th percentile of hedge-fund exposure and tend to fall together "
        "when funds cut leverage.",
        icon=":material/warning:",
    )
if len(crowded_bets):
    st.warning(
        "**Overweight where hedge funds are crowded:** "
        + ", ".join(f"{s} ({a * 100:+.1f} pp vs benchmark, {p:.0f}th percentile)"
                    for s, a, p in zip(crowded_bets.index, crowded_bets["active"], crowded_bets["percentile_3y"])),
        icon=":material/warning:",
    )

with grid("lev"):
    with st.container():
        section("Gross leverage", f"Hedge-fund gross exposure, % of equity · gray line: 3-year average, {lev['gross'].mean():.0%}")
        chart(*charts.pb_leverage("gross"), key="pb_gross")
    with st.container():
        section("Net leverage", f"Hedge-fund net exposure, % of equity · gray line: 3-year average, {lev['net'].mean():.0%}")
        chart(*charts.pb_leverage("net"), key="pb_net")

with grid("sectors"):
    with st.container():
        section("Sector positioning", "Hedge-fund net exposure as a 3-year percentile; above 50 is more than usual")
        chart(*charts.pb_sector_percentiles(), key="pb_sector")
    with st.container():
        section("Sector flows", "Weekly net buying z-score, last 12 weeks")
        chart(*charts.pb_flow_heatmap(), key="pb_flows")

section("Single-stock crowding", "Our holdings first, most crowded first")
only_held = st.toggle("Only our holdings", value=False)
table = crowd[crowd["held"]] if only_held else crowd
table = table.assign(crowded=table["crowded"].map({True: "▲ Crowded", False: ""}))
st.dataframe(
    gain_loss(table[["name", "sector", "weight", "crowding_pct", "crowded", "short_interest", "days_to_cover", "flow_z"]], ["flow_z"]),
    width="stretch",
    height=table_height(len(table)),
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", pinned=True),
        "name": "Name",
        "sector": "Sector",
        "weight": st.column_config.NumberColumn("Our weight", format="percent"),
        "crowding_pct": st.column_config.ProgressColumn("Crowding pct", format="%d", min_value=0, max_value=100,
                                                        help="Hedge-fund long exposure as a 3-year percentile"),
        "crowded": "Flag",
        "short_interest": st.column_config.NumberColumn("Short interest", format="percent", help="Share of float"),
        "days_to_cover": st.column_config.NumberColumn("Days to cover", format="%.1f"),
        "flow_z": st.column_config.NumberColumn("Flow z, WoW", format="%+.2f"),
    },
)
