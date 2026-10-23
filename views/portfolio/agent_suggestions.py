import numpy as np
import streamlit as st

from core import analytics as an
from core import config
from core.datasets import ACTIONS, SIGNALS
from core.ui import ACTION_COLOR, grid, header, kpis, section, table_height

header("Agent Suggestions", "Trade ideas from the research agent. Accepted ideas flow into Pro Forma")

status = st.session_state["suggestion_status"]
sugg = an.suggestions()
sugg["status"] = sugg["id"].map(status)
SIGNAL_NAMES = {s: s.removeprefix("sig_").replace("_", " ").capitalize().replace("Pb ", "PB ") for s in SIGNALS}


def set_status(sid: str, value: str) -> None:
    st.session_state["suggestion_status"][sid] = value


accepted = sugg[sugg["status"] == "accepted"]
kpis("agent", [
    {"label": "To review", "value": int((sugg["status"] == "pending").sum())},
    {"label": "Accepted", "value": len(accepted)},
    {"label": "Dismissed", "value": int((sugg["status"] == "dismissed").sum())},
    {"label": "Cash impact if accepted", "value": f"{-accepted['change'].sum() * 100 + 0.0:+.1f} pp",
     "help": "Change in cash weight if every accepted idea is traded"},
])

with st.container(horizontal=True, vertical_alignment="bottom"):
    actions = st.pills("Action", ACTIONS, selection_mode="multi", default=list(ACTIONS))
    view = st.segmented_control("Status", ["To review", "Accepted", "Dismissed", "All"], default="All", required=True)
    min_conf = st.slider("Min. confidence", 0, 100, 0, step=5, format="%d%%", width=200)
    st.space("stretch")
    st.page_link("views/portfolio/pro_forma.py", label="Open Pro Forma", icon=":material/tune:")

cal = an.catalysts()
next_ev = cal[(cal["days"] >= 0) & cal["ticker"].notna()].groupby("ticker").first()
sugg["next_event"] = [f"{next_ev.at[t, 'event_type']} in {next_ev.at[t, 'days']}d" if t in next_ev.index else ""
                      for t in sugg["ticker"]]

state_for = {"To review": "pending", "Accepted": "accepted", "Dismissed": "dismissed"}
shown = sugg[
    sugg["action"].isin(actions or [])
    & (sugg["confidence"] * 100 >= min_conf)
    & ((view == "All") | (sugg["status"] == state_for.get(view)))
]

section("Overview", f"{len(shown)} of {len(sugg)} ideas, highest confidence first · run {sugg['generated_at'].max():%d %b %H:%M}")
overview = shown.set_index("ticker")[["action", "current_weight", "target_weight", "confidence", "support", "against",
                                      "status", "next_event", "name"]]
overview = overview.assign(
    signals=[f"{s} for · {a} against" for s, a in zip(overview["support"], overview["against"])],
    status=overview["status"].map({"pending": "To review", "accepted": "✓ Accepted", "dismissed": "Dismissed"}),
)[["action", "current_weight", "target_weight", "confidence", "signals", "status", "next_event", "name"]]
st.dataframe(
    overview,
    width="stretch",
    height=table_height(len(overview)),
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", pinned=True),
        "action": "Action",
        "name": "Name",
        "current_weight": st.column_config.NumberColumn("Now", format="percent"),
        "target_weight": st.column_config.NumberColumn("Target", format="percent"),
        "confidence": st.column_config.ProgressColumn("Confidence", format="percent", min_value=0, max_value=1),
        "signals": "Signals",
        "status": "Status",
        "next_event": "Next event",
    },
)

section("Ideas", "Green signals support the idea, red ones argue against it; arrows show which way each signal points")
with grid("ideas"):
    for s in shown.itertuples():
        direction = 1 if s.action in ("Initiate", "Add") else -1
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(s.action, color=ACTION_COLOR[s.action])
                st.markdown(f"**{s.ticker}** · {s.name}")
                if s.status == "accepted":
                    st.badge("Accepted", icon=":material/check:", color="green")
                elif s.status == "dismissed":
                    st.badge("Dismissed", icon=":material/close:", color="gray")
            st.markdown(f"Weight **{s.current_weight:.1%} → {s.target_weight:.1%}** ({s.change * 100:+.1f} pp) · {s.horizon}")
            if s.ticker in next_ev.index:
                e = next_ev.loc[s.ticker]
                soon = e["bdays"] <= config.EVENT_WARNING_BDAYS
                st.caption(f"{':orange[:material/warning:]' if soon else ':material/event_upcoming:'} "
                           f"Next event: {e['title']} {e['date']:%a %d %b}, in {e['days']} days")
            st.progress(s.confidence, text=f"Confidence {s.confidence:.0%} · {s.support} of {len(SIGNALS)} signals support")
            st.markdown("\n".join(f"- {p}" for p in s.points))
            with st.container(horizontal=True, gap="small"):
                for sig in SIGNALS:
                    v = getattr(s, sig)
                    icon = {1: ":material/arrow_upward:", 0: ":material/remove:", -1: ":material/arrow_downward:"}[v]
                    color = {1: "green", 0: "gray", -1: "red"}[int(np.sign(v * direction))]
                    st.badge(SIGNAL_NAMES[sig], icon=icon, color=color)
            with st.container(horizontal=True):
                if s.status == "pending":
                    st.button("Accept", key=f"acc_{s.id}", type="primary", icon=":material/check:",
                              on_click=set_status, args=(s.id, "accepted"))
                    st.button("Dismiss", key=f"dis_{s.id}", icon=":material/close:",
                              on_click=set_status, args=(s.id, "dismissed"))
                else:
                    st.button("Undo", key=f"undo_{s.id}", icon=":material/undo:",
                              on_click=set_status, args=(s.id, "pending"))

if shown.empty:
    st.info("No ideas match these filters.", icon=":material/filter_alt_off:")
