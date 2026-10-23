"""Chart builders shared by the dashboards and the Slides & Charts library.

Each builder returns (figure, table) so every chart ships with a table view.
"""

import pandas as pd
import plotly.graph_objects as go

from core import analytics as an
from core import config
from core.data import load
from core.theme import diverging_scale, style, tokens


def _endpoint(fig: go.Figure, x, y, color: str, label: str) -> None:
    t = tokens()
    fig.add_scatter(
        x=[x], y=[y], mode="markers+text", text=[label], textposition="middle right",
        marker=dict(size=8, color=color, line=dict(width=2, color=t["surface"])),
        cliponaxis=False, showlegend=False, hoverinfo="skip",
    )


def performance(base: pd.Timestamp | None = None, height: int = 340) -> tuple[go.Figure, pd.DataFrame]:
    t = tokens()
    n = an.nav().loc[base:] if base is not None else an.nav()
    df = pd.DataFrame({
        "Portfolio": n["port_idx"] / n["port_idx"].iloc[0] - 1,
        config.BENCHMARK_NAME: n["bench_idx"] / n["bench_idx"].iloc[0] - 1,
    })
    fig = go.Figure()
    for name, color, rank in [(config.BENCHMARK_NAME, t["muted"], 2), ("Portfolio", t["series"][0], 1)]:
        fig.add_scatter(x=df.index, y=df[name], name=name, mode="lines", line_color=color,
                        legendrank=rank, hovertemplate="%{y:+.1%}")
        _endpoint(fig, df.index[-1], df[name].iloc[-1], color, f"{df[name].iloc[-1]:+.1%}")
    style(fig, height)
    fig.update_layout(hovermode="x unified", margin_r=64)
    fig.update_yaxes(tickformat="+.0%")
    return fig, df


def nav_with_decisions(selected: pd.Timestamp | None = None, height: int = 300) -> tuple[go.Figure, pd.DataFrame]:
    t = tokens()
    nav = an.nav()["nav"]
    dates = pd.DatetimeIndex(sorted(load("decisions")["decision_date"].unique()))
    fig = go.Figure()
    fig.add_scatter(x=nav.index, y=nav, name="NAV", mode="lines", line_color=t["series"][0],
                    hovertemplate="$%{y:,.0f}<extra>NAV</extra>")
    for d in dates:
        is_sel = selected is not None and d == selected
        fig.add_vline(x=d, line_width=2 if is_sel else 1, line_color=t["series"][1] if is_sel else t["baseline"])
    fig.add_scatter(
        x=dates, y=nav.reindex(dates), mode="markers", name="Decision",
        marker=dict(size=9, color=t["series"][1], line=dict(width=2, color=t["surface"])),
        hovertemplate="Decision %{x|%d %b %Y}<extra></extra>",
    )
    style(fig, height)
    fig.update_yaxes(tickprefix="$", tickformat=".3s")
    return fig, nav.to_frame("nav")


def diverging_bars(values: pd.Series, fmt, hover: str, height: int = 340,
                   base: float = 0.0, customdata=None) -> go.Figure:
    t = tokens()
    order = values.sort_values().index
    values = values.loc[order]
    fig = go.Figure(go.Bar(
        x=values, y=values.index, base=base, orientation="h", text=[fmt(v) for v in values],
        marker_color=[t["pos"] if v > 0 else t["neg"] for v in values],
        textposition="outside", cliponaxis=False, hovertemplate=hover,
        customdata=customdata.loc[order] if customdata is not None else None,
    ))
    style(fig, height, legend=False)
    # Pad the value axis so outside labels on either arm clear the tick labels.
    lo, hi = min(values.min(), 0), max(values.max(), 0)
    pad = (hi - lo) * 0.25
    fig.update_xaxes(range=[base + lo - (pad if lo < 0 else 0), base + hi + (pad if hi > 0 else 0)],
                     showgrid=True, gridcolor=t["grid"], zeroline=True, zerolinecolor=t["baseline"], zerolinewidth=1)
    fig.update_yaxes(showgrid=False, automargin=True)
    fig.update_layout(margin=dict(l=8, r=8, t=12, b=8))
    return fig


def _bar_height(n: int) -> int:
    return 60 + 30 * n


def contributors(start: pd.Timestamp, n: int = 5) -> tuple[go.Figure, pd.DataFrame]:
    c = an.contributions(start)
    top = pd.concat([c.head(n), c.tail(n)])
    top = top[~top.index.duplicated()].sort_values() * 1e4
    fig = diverging_bars(top, lambda v: f"{v:+.0f} bp", "%{y}: %{x:+.0f} bp<extra></extra>",
                         _bar_height(len(top)))
    return fig, top.to_frame("contribution_bp")


def day_movers(n: int = 4) -> tuple[go.Figure, pd.DataFrame]:
    h = an.holdings()
    pnl = h["day_pnl"].sort_values()
    top = pd.concat([pnl.head(n), pnl.tail(n)])
    top = top[~top.index.duplicated()]
    pct = h["day_change"].reindex(top.index)
    fig = diverging_bars(top, lambda v: f"{'+' if v >= 0 else '-'}${abs(v) / 1e3:,.0f}K",
                         "%{y}: $%{x:,.0f} (%{customdata:+.2%})<extra></extra>", _bar_height(len(top)), customdata=pct)
    fig.update_xaxes(tickprefix="$", tickformat="~s")
    return fig, pd.DataFrame({"day_pnl": top, "day_change": pct})


def weight_changes(delta: pd.Series) -> tuple[go.Figure, pd.DataFrame]:
    d = delta[delta.abs() > 1e-9] * 100
    fig = diverging_bars(d, lambda v: f"{v:+.1f} pp", "%{y}: %{x:+.2f} pp<extra></extra>",
                         _bar_height(len(d)))
    return fig, d.sort_values().to_frame("change_pp")


def active_sectors(weights: pd.Series | None = None) -> tuple[go.Figure, pd.DataFrame]:
    """Overweight / underweight vs benchmark by sector, in percentage points."""
    df = an.active_sectors(weights)
    pp = df["active"] * 100
    fig = diverging_bars(pp, lambda v: f"{v:+.1f}",
                         "%{y}: %{x:+.1f} pp<br>Portfolio %{customdata[0]:.1%} · Benchmark %{customdata[1]:.1%}<extra></extra>",
                         _bar_height(len(pp)), customdata=df[["portfolio", "benchmark"]].apply(tuple, axis=1))
    fig.update_xaxes(ticksuffix=" pp")
    return fig, df


def sector_shift(current: pd.Series, proforma: pd.Series) -> tuple[go.Figure, pd.DataFrame]:
    """Dumbbell of active sector weight, today vs pro forma."""
    t = tokens()
    df = pd.DataFrame({"Current": an.active_sectors(current)["active"],
                       "Pro forma": an.active_sectors(proforma)["active"]}).fillna(0.0) * 100
    df = df.sort_values("Pro forma")
    fig = go.Figure()
    for s, row in df.iterrows():
        fig.add_scatter(x=[row["Current"], row["Pro forma"]], y=[s, s], mode="lines",
                        line=dict(color=t["baseline"], width=2), showlegend=False, hoverinfo="skip")
    for name, color in [("Current", t["muted"]), ("Pro forma", t["series"][0])]:
        fig.add_scatter(x=df[name], y=df.index, mode="markers", name=name,
                        marker=dict(size=10, color=color, line=dict(width=2, color=t["surface"])),
                        hovertemplate="%{y}: %{x:+.1f} pp<extra>" + name + "</extra>")
    style(fig, _bar_height(len(df)) + 20)
    fig.update_xaxes(ticksuffix=" pp", showgrid=True, gridcolor=t["grid"], zeroline=True,
                     zerolinecolor=t["baseline"], zerolinewidth=1)
    fig.update_yaxes(showgrid=False, automargin=True)
    return fig, df


def alt_trend(ticker: str, metric: str, height: int = 220) -> tuple[go.Figure, pd.DataFrame]:
    t = tokens()
    df = load("alt_data").query("ticker == @ticker and metric == @metric").set_index("week").sort_index()[["yoy"]]
    fig = go.Figure(go.Scatter(x=df.index, y=df["yoy"], mode="lines", line_color=t["series"][0],
                               name=metric, hovertemplate="%{x|%d %b %Y}: %{y:+.1%}<extra></extra>"))
    _endpoint(fig, df.index[-1], df["yoy"].iloc[-1], t["series"][0], f"{df['yoy'].iloc[-1]:+.1%}")
    fig.add_hline(y=0, line_width=1, line_color=t["baseline"])
    style(fig, height, legend=False)
    fig.update_layout(margin_r=56)
    fig.update_yaxes(tickformat="+.0%")
    return fig, df


def _heatmap(z: pd.DataFrame, fmt: str, hover: str, height: int, zmax: float | None = None) -> go.Figure:
    zmax = zmax or float(z.abs().max().max())
    fig = go.Figure(go.Heatmap(
        z=z.values, x=list(z.columns), y=list(z.index), colorscale=diverging_scale(),
        zmin=-zmax, zmax=zmax, zmid=0, texttemplate=fmt, xgap=2, ygap=2,
        hovertemplate=hover, colorbar=dict(thickness=10, outlinewidth=0),
    ))
    style(fig, height, legend=False)
    fig.update_xaxes(side="top", showline=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    return fig


def alt_heatmap(height: int | None = None) -> tuple[go.Figure, pd.DataFrame]:
    s = an.alt_signals()
    z = s[[m for m in s.columns if m in ("Card spend", "App MAU", "Web visits")]]
    fig = _heatmap(z, "%{z:+.0%}", "%{y} · %{x}: %{z:+.1%} YoY<extra></extra>", height or 60 + 26 * len(z))
    fig.update_traces(colorbar_tickformat="+.0%")
    return fig, z


def pb_leverage(column: str, height: int = 240) -> tuple[go.Figure, pd.DataFrame]:
    t = tokens()
    s = an.pb_leverage()[column] * 100
    avg = s.mean()
    fig = go.Figure(go.Scatter(x=s.index, y=s, mode="lines", line_color=t["series"][0],
                               hovertemplate="%{x|%d %b %Y}: %{y:.1f}%<extra></extra>"))
    fig.add_hline(y=avg, line_width=1, line_color=t["muted"])
    _endpoint(fig, s.index[-1], s.iloc[-1], t["series"][0], f"{s.iloc[-1]:.0f}%")
    style(fig, height, legend=False)
    fig.update_layout(margin_r=48)
    fig.update_yaxes(ticksuffix="%")
    return fig, s.to_frame(f"{column}_pct")


def pb_sector_percentiles() -> tuple[go.Figure, pd.DataFrame]:
    s = an.pb_sectors()
    pct = s["percentile_3y"]
    fig = diverging_bars(pct - 50, lambda v: f"{v + 50:.0f}th", "", _bar_height(len(pct)), base=50,
                         customdata=s[["percentile_3y", "active"]].apply(tuple, axis=1))
    fig.update_traces(hovertemplate="%{y}: %{customdata[0]:.0f}th percentile<br>Our active weight %{customdata[1]:+.1%}<extra></extra>")
    fig.update_xaxes(range=[0, 108], zeroline=False, tickvals=[0, 25, 50, 75, 100])
    fig.add_vline(x=50, line_width=1, line_color=tokens()["baseline"])
    return fig, s[["percentile_3y", "net_share", "active"]]


def pb_flow_heatmap() -> tuple[go.Figure, pd.DataFrame]:
    z = an.pb_flows()
    z.columns = [f"{c:%d %b}" for c in z.columns]
    fig = _heatmap(z, "%{z:.1f}", "%{y} · week of %{x}: z = %{z:.2f}<extra></extra>", 60 + 30 * len(z), zmax=2.5)
    fig.update_xaxes(tickangle=-45)
    return fig, z


def group_colors() -> dict:
    """Who an event matters to. Scatter forms validate only the first three slots, so the rest is gray."""
    t = tokens()
    return {"Market": t["series"][2], "Holding": t["series"][0], "Agent idea": t["series"][1], "Watchlist": t["muted"]}


def catalyst_timeline(events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[go.Figure, pd.DataFrame]:
    """One row per name, one marker per event: color = who it matters to, circle = earnings, size = importance."""
    t = tokens()
    ev = events.assign(row=events["ticker"].fillna("Market"))
    order = ev.sort_values(["group", "weight"], ascending=[True, False]).drop_duplicates("row")["row"].tolist()
    colors = group_colors()
    size = {"High": 15, "Medium": 11, "Low": 8}
    fig = go.Figure()
    for g in an.GROUPS:
        sub = ev[ev["group"] == g]
        if sub.empty:
            continue
        # Legend-only swatch, so the legend shows color = group rather than the first event's shape.
        fig.add_scatter(x=[None], y=[None], mode="markers", name=g, legendgroup=g,
                        marker=dict(color=colors[g], size=10, symbol="square"))
        fig.add_scatter(
            x=sub["date"], y=sub["row"], mode="markers", name=g, legendgroup=g, showlegend=False,
            marker=dict(color=colors[g], size=sub["importance"].astype(str).map(size).tolist(),
                        symbol=["circle" if e == "Earnings" else "diamond" for e in sub["event_type"]],
                        line=dict(width=2, color=t["surface"])),
            customdata=sub[["title", "event_type"]].assign(importance=sub["importance"].astype(str)).to_numpy(),
            hovertemplate="<b>%{y}</b> · %{x|%a %d %b}<br>%{customdata[0]}<br>%{customdata[1]} · %{customdata[2]} importance<extra></extra>",
        )
    fig.add_vline(x=start, line_width=1, line_color=t["baseline"])
    style(fig, 70 + 26 * len(order))
    # Explicit axis types: the empty legend swatches come first and would otherwise make both axes numeric.
    fig.update_xaxes(type="date", range=[start - pd.Timedelta(days=1), end + pd.Timedelta(days=1)], tickformat="%d %b",
                     showgrid=True, gridcolor=t["grid"])
    fig.update_yaxes(type="category", categoryorder="array", categoryarray=order[::-1], showgrid=True,
                     gridcolor=t["grid"], automargin=True)
    return fig, ev[["date", "row", "event_type", "title", "importance", "group"]].set_index("date")


def _holding_catalysts(days: int = 30) -> tuple[go.Figure, pd.DataFrame]:
    ev = an.upcoming(days)
    ev = ev[ev["group"].isin(["Market", "Holding"])]
    return catalyst_timeline(ev, an.today(), an.today() + pd.Timedelta(days=days))


def _ytd() -> pd.Timestamp:
    return pd.Timestamp(an.as_of().year, 1, 1)


LIBRARY = [
    {"id": "performance", "title": "Performance vs benchmark", "category": "Portfolio",
     "description": "Cumulative return since inception, portfolio against benchmark.",
     "build": lambda: performance()},
    {"id": "sectors", "title": "Sector bets vs benchmark", "category": "Portfolio",
     "description": "Active weight by sector: portfolio minus benchmark, in percentage points.",
     "build": lambda: active_sectors()},
    {"id": "contributors", "title": "YTD contributors & detractors", "category": "Portfolio",
     "description": "Largest positive and negative contributions to return this year, in basis points.",
     "build": lambda: contributors(_ytd())},
    {"id": "decisions", "title": "NAV and decision dates", "category": "Portfolio",
     "description": "Portfolio NAV with each investment-committee decision marked.",
     "build": lambda: nav_with_decisions()},
    {"id": "catalysts", "title": "Catalysts, next 30 days", "category": "Research",
     "description": "Upcoming events for our holdings and the market. Circles are earnings; larger is more important.",
     "build": lambda: _holding_catalysts()},
    {"id": "alt_heatmap", "title": "Alternative data: latest YoY", "category": "Research",
     "description": "4-week average YoY growth by ticker across card spend, app MAU and web visits.",
     "build": lambda: alt_heatmap()},
    {"id": "pb_net", "title": "Hedge-fund net leverage", "category": "Research",
     "description": "Prime-broker net leverage over three years against its average.",
     "build": lambda: pb_leverage("net")},
    {"id": "pb_sectors", "title": "PB sector positioning", "category": "Research",
     "description": "Hedge-fund net exposure by sector as a 3-year percentile.",
     "build": lambda: pb_sector_percentiles()},
    {"id": "pb_flows", "title": "PB sector flows", "category": "Research",
     "description": "Weekly net buying z-score by sector, last 12 weeks.",
     "build": lambda: pb_flow_heatmap()},
]

LIBRARY_BY_ID = {c["id"]: c for c in LIBRARY}
