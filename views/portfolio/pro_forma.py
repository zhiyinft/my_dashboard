import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts, config
from core.ui import accepted_suggestions, chart, gain_loss, grid, header, kpis, money, section, table_height

header("Pro Forma", "The book after proposed trades, checked against limits before anything is sent")

h = an.holdings()
sec = an.securities()
nav_now = an.nav()["nav"].iloc[-1]
accepted = accepted_suggestions()

base = sec[["name", "sector"]].copy()
base["current"] = (h["weight"].reindex(base.index).fillna(0.0) * 100).round(2)
base["target"] = base["current"]
base["source"] = ""
for s in accepted.itertuples():
    base.at[s.ticker, "target"] = round(s.target_weight * 100, 2)
    base.at[s.ticker, "source"] = f"Agent {s.id}"

with st.container(horizontal=True, vertical_alignment="center"):
    show_all = st.toggle("Show names not in the book", value=False)
    if st.button("Reset edits", icon=":material/restart_alt:"):
        st.session_state["pf_nonce"] = st.session_state.get("pf_nonce", 0) + 1
    st.caption(f"{len(accepted)} accepted agent idea(s) applied" if len(accepted) else "No agent ideas accepted yet")
    st.page_link("views/portfolio/agent_suggestions.py", label="Agent suggestions", icon=":material/smart_toy:")

summary = st.container()

rows = base if show_all else base[(base["current"] > 0) | (base["target"] > 0)]
rows = rows.sort_values(["current", "target"], ascending=False)
editor_key = f"pf_editor_{'-'.join(accepted['id'])}_{st.session_state.get('pf_nonce', 0)}_{show_all}"

with grid("pf", "wide"):
    with st.container():
        section("Target weights", "Edit Target % to try a trade; everything else updates as you type")
        edited = st.data_editor(
            rows[["current", "target", "name", "sector", "source"]],
            key=editor_key,
            width="stretch",
            height=table_height(len(rows)),
            disabled=["name", "sector", "current", "source"],
            column_config={
                "ticker": st.column_config.TextColumn("Ticker", pinned=True),
                "name": "Name",
                "sector": "Sector",
                "current": st.column_config.NumberColumn("Now %", format="%.2f"),
                "target": st.column_config.NumberColumn("Target %", format="%.2f", min_value=0.0, max_value=25.0, step=0.25),
                "source": "Source",
            },
        )
    right = st.container()

target = base["target"].copy()
target.loc[edited.index] = edited["target"].fillna(0.0)
current, target = base["current"] / 100, target / 100
delta = target - current
changes = delta[delta.abs() > 1e-9]
cur_held, pf_held = current[current > 0], target[target > 0]
cash_now, cash_pf = 1 - current.sum(), 1 - target.sum()
beta_now, beta_pf = (current * sec["beta"]).sum(), (target * sec["beta"]).sum()
top_now, top_pf = cur_held.nlargest(10).sum(), pf_held.nlargest(10).sum()

def vs_now(now: float, pf: float, digits: int, unit: str = "") -> dict:
    """st.metric delta kwargs comparing the values as displayed, so 1.13 -> 1.14 never reads 'No change'."""
    diff = round(pf, digits) - round(now, digits)
    if abs(diff) < 10 ** -(digits + 1):
        return {"delta": "No change", "delta_color": "off", "delta_arrow": "off"}
    return {"delta": f"{diff:+.{digits}f}{unit} vs now", "delta_color": "off"}


with summary:
    kpis("pf", [
        {"label": "Positions", "value": len(pf_held), **vs_now(len(cur_held), len(pf_held), 0)},
        {"label": "Cash", "value": f"{cash_pf:.1%}", **vs_now(cash_now * 100, cash_pf * 100, 1, " pp")},
        {"label": "Top-10 weight", "value": f"{top_pf:.1%}", **vs_now(top_now * 100, top_pf * 100, 1, " pp")},
        {"label": "Beta", "value": f"{beta_pf:.2f}", **vs_now(beta_now, beta_pf, 2)},
        {"label": "Gross trades", "value": money(delta.abs().sum() * nav_now),
         "delta": f"{delta.abs().sum():.1%} of NAV", "delta_color": "off", "delta_arrow": "off"},
    ])
    section("Pre-trade checks")
    with grid("checks", "cards"):
        for c in an.pre_trade_checks(target):
            with st.container(border=True):
                icon = ":green[:material/check_circle:]" if c["ok"] else ":red[:material/cancel:]"
                st.markdown(f"{icon} **{c['label']}** · {c['value']}")
                st.caption(f"{'Within' if c['ok'] else 'Breaks'} limit: {c['limit']}")

with right:
    section("Sector bets, now vs pro forma", "Active weight against the benchmark, percentage points")
    chart(*charts.sector_shift(cur_held, pf_held), key="pf_sectors")
    if len(changes):
        section("Weight changes", "Percentage points")
        chart(*charts.weight_changes(changes), key="pf_changes")

section("Trade list", "What would be sent, at the last close")
if changes.empty:
    st.info("No changes yet. Edit a Target % above or accept an idea in Agent Suggestions.", icon=":material/info:")
else:
    px_last = an.prices_wide().iloc[-1]
    notional = changes * nav_now
    trade_list = pd.DataFrame({
        "side": ["Buy" if v > 0 else "Sell" for v in changes],
        "name": base.loc[changes.index, "name"],
        "from": current[changes.index],
        "to": target[changes.index],
        "notional": notional / 1e6,
        "shares": (notional / px_last[changes.index]).round(0),
        "source": base.loc[changes.index, "source"].replace("", "Manual"),
    }).sort_values("notional")
    st.dataframe(
        gain_loss(trade_list, ["notional", "shares"]),
        width="stretch",
        height=table_height(len(trade_list)),
        column_config={
            "ticker": "Ticker",
            "side": "Side",
            "name": "Name",
            "from": st.column_config.NumberColumn("From", format="percent"),
            "to": st.column_config.NumberColumn("To", format="percent"),
            "notional": st.column_config.NumberColumn("Notional $M", format="%+.2f"),
            "shares": st.column_config.NumberColumn("Shares", format="%+d"),
            "source": "Source",
        },
    )
