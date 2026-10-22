import pandas as pd
import streamlit as st

from core import analytics as an
from core import charts
from core.ui import CHART_CONFIG, accepted_suggestions, header, money

header("Presentation", "Deck built from the charts picked in Slides & Charts")


def takeaway(chart_id: str) -> str:
    ytd = pd.Timestamp(an.as_of().year, 1, 1)
    if chart_id == "performance":
        n = an.nav()
        return (f"Since inception the portfolio returned {n['port_idx'].iloc[-1] - 1:+.1%} "
                f"against {n['bench_idx'].iloc[-1] - 1:+.1%} for the benchmark.")
    if chart_id == "sectors":
        a = an.active_sectors()["active"]
        return (f"Largest overweight is {a.idxmax()} ({a.max() * 100:+.1f} pp); "
                f"largest underweight is {a.idxmin()} ({a.min() * 100:+.1f} pp).")
    if chart_id == "contributors":
        c = an.contributions(ytd)
        return f"{c.index[-1]} added the most this year ({c.iloc[-1] * 1e4:+.0f} bp); {c.index[0]} cost the most ({c.iloc[0] * 1e4:+.0f} bp)."
    if chart_id == "decisions":
        d = an.decision_outcomes()
        return f"{len(d)} trades across {d['decision_date'].nunique()} decisions, with a {d['worked'].mean():.0%} hit rate."
    if chart_id == "alt_heatmap":
        s = an.alt_signals()
        acc = ", ".join(s.index[s["signal"] == "Accelerating"]) or "none"
        dec = ", ".join(s.index[s["signal"] == "Decelerating"]) or "none"
        return f"Accelerating: {acc}. Decelerating: {dec}."
    if chart_id == "pb_net":
        lev = an.pb_leverage()["net"]
        return f"Net leverage is {lev.iloc[-1]:.0%}, against a 3-year average of {lev.mean():.0%}."
    if chart_id == "pb_sectors":
        s = an.pb_sectors()["percentile_3y"]
        return f"Most crowded: {s.idxmax()} ({s.max():.0f}th percentile). Least owned: {s.idxmin()} ({s.min():.0f}th)."
    if chart_id == "pb_flows":
        z = an.pb_flows().iloc[:, -1]
        return f"Last week's strongest buying was in {z.idxmax()} (z = {z.max():.1f}), heaviest selling in {z.idxmin()} (z = {z.min():.1f})."
    return ""


slides = [{"kind": "title", "title": f"Portfolio Review · {an.as_of():%B %Y}"}]
slides += [{"kind": "chart", "id": cid, "title": charts.LIBRARY_BY_ID[cid]["title"]} for cid in st.session_state["deck"]]
slides.append({"kind": "next", "title": "Next steps"})
n = len(slides)
st.session_state["slide"] = min(st.session_state["slide"], n - 1)


def go(step: int) -> None:
    st.session_state["slide"] = max(0, min(n - 1, st.session_state["slide"] + step))


with st.container(horizontal=True, vertical_alignment="center"):
    st.button("Previous", icon=":material/chevron_left:", on_click=go, args=(-1,), disabled=st.session_state["slide"] == 0)
    st.segmented_control("Slide", list(range(n)), key="slide", format_func=lambda i: str(i + 1),
                         required=True, label_visibility="collapsed")
    st.button("Next", icon=":material/chevron_right:", icon_position="right", on_click=go, args=(1,),
              disabled=st.session_state["slide"] == n - 1)
    st.space("stretch")
    st.page_link("views/content/slides_charts.py", label="Edit deck", icon=":material/edit:")

slide = slides[st.session_state["slide"]]
with st.container(border=True):
    if slide["kind"] == "title":
        st.space("medium")
        st.title(slide["title"])
        st.caption("Public Portfolio · Investment Committee")
        nav = an.nav()
        base = an.period_base(pd.Timestamp(an.as_of().year, 1, 1))
        ytd, ytd_b = an.period_returns(base)
        c1, c2, c3 = st.columns(3)
        c1.metric("NAV", money(nav["nav"].iloc[-1]))
        c2.metric("YTD return", f"{ytd:+.1%}", f"{(ytd - ytd_b) * 100:+.1f} pp vs benchmark")
        c3.metric("Positions", len(an.holdings()))
        st.space("medium")
    elif slide["kind"] == "chart":
        item = charts.LIBRARY_BY_ID[slide["id"]]
        st.subheader(slide["title"])
        st.markdown(f"**{takeaway(slide['id'])}**")
        fig, _ = item["build"]()
        fig.update_layout(height=max(fig.layout.height or 0, 420))
        st.plotly_chart(fig, key=f"slide_{slide['id']}", config=CHART_CONFIG)
        st.caption(item["description"])
    else:
        st.subheader(slide["title"])
        accepted = accepted_suggestions()
        if len(accepted):
            st.markdown("\n".join(
                f"- **{s.action} {s.ticker}** to {s.target_weight:.1%}: {s.points[0]}" for s in accepted.itertuples()
            ))
        else:
            st.markdown("- No agent ideas accepted yet. Review them in **Agent Suggestions**.")
        crowd = an.crowding()
        crowded = crowd[crowd["held"] & crowd["crowded"]]
        if len(crowded):
            st.markdown(f"- Review crowded longs: {', '.join(crowded.index)} ({crowded['weight'].sum():.1%} of NAV)")
        st.markdown("- Next committee meeting: first week of next month")
