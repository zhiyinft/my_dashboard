import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts
from core.ui import ACTION_COLOR, chart, gain_loss, grid, header, kpis, outcome_badge, section, table_height

header("Decision Date", "What the investment committee decided, why, and how it has played out")

dec = an.decision_outcomes()
dates = sorted(pd.to_datetime(dec["decision_date"].unique()), reverse=True)
st.session_state.setdefault("dd_date", dates[0])


def step(offset: int) -> None:
    i = dates.index(st.session_state["dd_date"]) + offset
    st.session_state["dd_date"] = dates[max(0, min(len(dates) - 1, i))]


with st.container(horizontal=True, vertical_alignment="bottom"):
    st.selectbox("Decision date", dates, key="dd_date", width=300,
                 format_func=lambda x: f"{x:%d %b %Y} · {(an.as_of() - x).days} days ago")
    pos = dates.index(st.session_state["dd_date"])
    st.button("Older", icon=":material/chevron_left:", on_click=step, args=(1,), disabled=pos == len(dates) - 1)
    st.button("Newer", icon=":material/chevron_right:", icon_position="right", on_click=step, args=(-1,), disabled=pos == 0)

d = st.session_state["dd_date"]
day = dec[dec["decision_date"] == d]

kpis("dd", [
    {"label": "Trades", "value": len(day)},
    {"label": "Turnover", "value": f"{day['delta'].abs().sum():.1%}", "help": "Sum of absolute weight changes"},
    {"label": "Hit rate", "value": f"{day['worked'].mean():.0%}", "help": "Buys that beat the benchmark since, sells that lagged it"},
    {"label": "Value added", "value": f"{day['value_added'].mean() * 100:+.1f} pp",
     "help": "Average excess return since the decision, sign-flipped for sells"},
])

section("What was decided", "Return since is measured from the decision-day close to the latest close")
with grid("decided", "cards"):
    for tr in day.itertuples():
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(tr.action, color=ACTION_COLOR[tr.action])
                outcome_badge(bool(tr.worked))
            st.markdown(f"**{tr.ticker}** · {tr.name}")
            st.markdown(f"Weight **{tr.weight_before:.1%} → {tr.weight_after:.1%}**")
            st.caption(tr.rationale)
            st.markdown(f"Stock {tr.return_since:+.1%} · benchmark {tr.bench_since:+.1%}  \n"
                        f"Value added **{tr.value_added * 100:+.1f} pp**")

book = an.book_around(d).sort_values("after", ascending=False)
with grid("book", "wide"):
    with st.container():
        section("Book before and after", "Weights at the decision-day close")
        # Change is formatted by the Styler (blank when unchanged), so it has no column_config entry.
        shown = book.rename(columns={"change": "Change"})
        st.dataframe(
            gain_loss(shown, ["Change"]).format(lambda v: "" if abs(v) < 5e-5 else f"{v:+.2%}", subset=["Change"]),
            width="stretch",
            height=table_height(len(book)),
            column_config={
                "ticker": "Ticker",
                "before": st.column_config.NumberColumn("Before", format="percent"),
                "after": st.column_config.ProgressColumn("After", format="percent", min_value=0, max_value=0.10),
            },
        )
    with st.container():
        section("Weight changes", "Percentage points")
        chart(*charts.weight_changes(book["change"].drop("CASH")), key="dd_changes")

section("Scorecard, all decisions", "Select a row to open that decision")
score = dec.groupby("decision_date").agg(
    trades=("ticker", "count"),
    what=("ticker", lambda s: ", ".join(f"{a} {t}" for a, t in zip(dec.loc[s.index, "action"], s))),
    hit_rate=("worked", "mean"),
    value_added=("value_added", "mean"),
    turnover=("delta", lambda s: s.abs().sum()),
).sort_index(ascending=False)


def pick(order=tuple(score.index)) -> None:
    rows = st.session_state["dd_score"].selection.rows
    if rows:
        st.session_state["dd_date"] = order[rows[0]]


st.dataframe(
    gain_loss(score.assign(value_added=score["value_added"] * 100).rename(index=lambda x: f"{x:%d %b %Y}"), ["value_added"]),
    width="stretch",
    height=table_height(len(score)),
    key="dd_score",
    on_select=pick,
    selection_mode="single-row",
    column_config={
        "decision_date": "Date",
        "trades": st.column_config.NumberColumn("Trades", width="small"),
        "what": st.column_config.TextColumn("What"),
        "hit_rate": st.column_config.ProgressColumn("Hit rate", format="percent", min_value=0, max_value=1),
        "value_added": st.column_config.NumberColumn("Value added", format="%+.1f pp"),
        "turnover": st.column_config.NumberColumn("Turnover", format="percent"),
    },
)

section("NAV and decision dates", "The selected decision is highlighted")
chart(*charts.nav_with_decisions(d), key="dd_nav")
