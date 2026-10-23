import streamlit as st

from core import analytics as an
from core.theme import is_dark
from core.ui import data_badge, init_state, inject_css

st.set_page_config(page_title="NFTrinity Dashboard", page_icon="assets/mark.png", layout="wide")
st.logo("assets/logo-dark.png" if is_dark() else "assets/logo-light.png", size="large", icon_image="assets/mark.png")
inject_css()
init_state()

pages = {
    "Public Portfolio": [
        st.Page("views/portfolio/live_portfolio.py", title="Live Portfolio", icon=":material/monitoring:", default=True),
        st.Page("views/portfolio/decision_date.py", title="Decision Date", icon=":material/event:"),
        st.Page("views/portfolio/portfolio_tbd.py", title="Portfolio (TBD)", icon=":material/help:"),
        st.Page("views/portfolio/pro_forma.py", title="Pro Forma", icon=":material/tune:"),
        st.Page("views/portfolio/agent_suggestions.py", title="Agent Suggestions", icon=":material/smart_toy:"),
    ],
    "Content": [
        st.Page("views/content/slides_charts.py", title="Slides & Charts", icon=":material/bar_chart:"),
        st.Page("views/content/presentation.py", title="Presentation", icon=":material/slideshow:"),
    ],
    "Research": [
        st.Page("views/research/catalysts.py", title="Catalysts", icon=":material/event_upcoming:"),
        st.Page("views/research/alt_data.py", title="Alternative Data", icon=":material/insights:"),
        st.Page("views/research/pb_positioning.py", title="Prime Broker Positioning", icon=":material/account_balance:"),
    ],
}

nav = st.navigation(pages, position="sidebar", expanded=True)

with st.sidebar:
    data_badge()
    st.caption(f"As of close {an.as_of():%a %d %b %Y}")

nav.run()
