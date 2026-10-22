import streamlit as st

from core.ui import header

header("Portfolio (TBD)", "Placeholder: this tab's purpose hasn't been decided yet")

st.info(
    "This tab was listed as **Portfolio ?** in the brief. Some candidates it could hold:\n\n"
    "- **Risk & exposures**: factor exposures, tracking error, VaR, liquidity\n"
    "- **Attribution**: Brinson sector allocation vs selection effects\n"
    "- **Holdings history**: how each position's weight evolved over time\n"
    "- **Watchlist**: names under review that aren't in the book yet",
    icon=":material/lightbulb:",
)
