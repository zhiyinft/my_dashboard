import streamlit as st

from core import charts
from core.ui import CHART_CONFIG, grid, header

header("Slides & Charts", "Chart library for decks. Tick a chart to add it to the Presentation")


def toggle(chart_id: str) -> None:
    deck = st.session_state["deck"]
    if chart_id in deck:
        deck.remove(chart_id)
    else:
        deck.append(chart_id)


deck = st.session_state["deck"]
with st.container(horizontal=True, vertical_alignment="bottom"):
    category = st.segmented_control("Category", ["All", "Portfolio", "Research"], default="All", required=True)
    st.space("stretch")
    st.page_link("views/content/presentation.py", label="Open presentation", icon=":material/slideshow:")

st.markdown(
    f"**Deck, {len(deck)} chart(s):** "
    + (" → ".join(f"{i + 1}. {charts.LIBRARY_BY_ID[c]['title']}" for i, c in enumerate(deck)) or "empty")
)

items = [c for c in charts.LIBRARY if category == "All" or c["category"] == category]
with grid("library"):
    for item in items:
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.caption(f"{item['category']} · {item['description']}")
            fig, _ = item["build"]()
            fig.update_layout(height=320)
            st.plotly_chart(fig, key=f"lib_{item['id']}", config=CHART_CONFIG)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.toggle("In deck", value=item["id"] in deck, key=f"deck_{item['id']}",
                          on_change=toggle, args=(item["id"],))
                st.space("stretch")
                st.download_button("HTML", fig.to_html(include_plotlyjs="cdn"), file_name=f"{item['id']}.html",
                                   mime="text/html", icon=":material/download:", key=f"dl_{item['id']}",
                                   on_click="ignore", type="tertiary")
