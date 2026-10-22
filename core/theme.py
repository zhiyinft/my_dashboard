"""Chart colors and shared Plotly styling.

Palette slots are assigned in fixed order and follow the entity, never its rank.
Light and dark are separate validated steps of the same hues; the active one is
picked from the viewer's Streamlit theme.
"""

import plotly.graph_objects as go
import streamlit as st

LIGHT = {
    "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
    "pos": "#2a78d6",
    "neg": "#e34948",
    "mid": "#f0efec",
    "text2": "#52514e",
    "surface": "#fcfcfb",
}

DARK = {
    "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
    "muted": "#898781",
    "grid": "#2c2c2a",
    "baseline": "#383835",
    "pos": "#3987e5",
    "neg": "#e66767",
    "mid": "#383835",
    "text2": "#c3c2b7",
    "surface": "#1a1a19",
}


def is_dark() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def tokens() -> dict:
    return DARK if is_dark() else LIGHT


def diverging_scale() -> list:
    t = tokens()
    return [[0.0, t["neg"]], [0.5, t["mid"]], [1.0, t["pos"]]]


def style(fig: go.Figure, height: int = 340, legend: bool = True) -> go.Figure:
    t = tokens()
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36 if legend else 12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        barcornerradius=4,
        bargap=0.25,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=dict(namelength=-1),
    )
    fig.update_xaxes(showgrid=False, linecolor=t["baseline"], zeroline=False, title=None)
    fig.update_yaxes(gridcolor=t["grid"], gridwidth=1, zeroline=False, title=None)
    fig.update_traces(selector=dict(type="scatter"), line_width=2)
    return fig
