"""Everything the pages show that is calculated rather than loaded.

All inputs come through core.data.load, so these work the same on mock and live data.
"""

import numpy as np
import pandas as pd

from core import config
from core.data import load
from core.datasets import SIGNALS

BUY = ("Initiate", "Add")


def prices_wide() -> pd.DataFrame:
    return load("prices").pivot(index="date", columns="ticker", values="close").sort_index()


def benchmark() -> pd.Series:
    return load("benchmark").set_index("date")["level"].sort_index()


def securities() -> pd.DataFrame:
    sec = load("securities").set_index("ticker")
    if "beta" not in sec or sec["beta"].isna().any():
        r = prices_wide().pct_change().iloc[-252:]
        b = benchmark().pct_change().reindex(r.index)
        est = r.apply(lambda s: s.cov(b) / b.var())
        sec["beta"] = sec["beta"].fillna(est) if "beta" in sec else est
    return sec


def as_of() -> pd.Timestamp:
    return load("nav")["date"].max()


def nav() -> pd.DataFrame:
    """Daily NAV with flow-adjusted portfolio returns and benchmark returns on the same dates."""
    n = load("nav").set_index("date").sort_index()
    flow = n["flow"].fillna(0.0) if "flow" in n else 0.0
    bench = benchmark().reindex(n.index).ffill()
    out = pd.DataFrame({"nav": n["nav"], "cash": n["cash"]})
    out["port_ret"] = ((n["nav"] - flow) / n["nav"].shift(1) - 1).fillna(0.0)
    out["bench_ret"] = bench.pct_change().fillna(0.0)
    out["port_idx"] = (1 + out["port_ret"]).cumprod()
    out["bench_idx"] = (1 + out["bench_ret"]).cumprod()
    return out


def period_base(start: pd.Timestamp | None) -> pd.Timestamp:
    """The close the period's return is measured from: the last close before start."""
    idx = nav().index
    return idx[idx < start][-1] if start is not None and (idx < start).any() else idx[0]


def period_returns(base: pd.Timestamp) -> tuple[float, float]:
    n = nav()
    return (n["port_idx"].iloc[-1] / n.at[base, "port_idx"] - 1,
            n["bench_idx"].iloc[-1] / n.at[base, "bench_idx"] - 1)


def quantities() -> pd.DataFrame:
    """Shares held at each close, date x ticker, zero when not held."""
    q = load("positions").pivot(index="date", columns="ticker", values="quantity")
    return q.reindex(nav().index).fillna(0.0)


def weights_daily() -> pd.DataFrame:
    q = quantities()
    px = prices_wide().reindex(index=q.index, columns=q.columns).ffill()
    return (q * px).div(nav()["nav"], axis=0)


def contributions(start: pd.Timestamp) -> pd.Series:
    """Each name's contribution to portfolio return from start to the latest close (decimal)."""
    w = weights_daily()
    r = prices_wide().reindex(index=w.index, columns=w.columns).pct_change()
    c = (w.shift(1) * r).loc[start:].sum()
    return c[c.abs() > 0].sort_values()


def holdings() -> pd.DataFrame:
    pos = load("positions")
    d = pos["date"].max()
    cur = pos[pos["date"] == d].set_index("ticker")
    px = prices_wide()
    last = px.loc[d, cur.index]
    prev = px.loc[px.index[px.index < d][-1], cur.index]
    sec = securities()
    nav_now = nav()["nav"].iloc[-1]
    q = cur["quantity"]
    df = pd.DataFrame({
        "name": sec["name"].reindex(cur.index),
        "sector": sec["sector"].reindex(cur.index),
        "quantity": q,
        "last": last,
        "market_value": q * last,
        "day_change": last / prev - 1,
        "day_pnl": q * (last - prev),
        "beta": sec["beta"].reindex(cur.index),
    })
    df["weight"] = df["market_value"] / nav_now
    if "avg_cost" in cur:
        df["avg_cost"] = cur["avg_cost"]
        df["total_return"] = last / cur["avg_cost"] - 1
        df["total_pnl"] = q * (last - cur["avg_cost"])
    df["trend_3m"] = [px[t].iloc[-63:].round(2).tolist() for t in df.index]
    return df.sort_values("weight", ascending=False)


def cash_weight() -> float:
    n = nav()
    return n["cash"].iloc[-1] / n["nav"].iloc[-1]


def decision_outcomes() -> pd.DataFrame:
    """Committee trades with how each one has done since, against the benchmark."""
    dec = load("decisions").copy()
    px, bench = prices_wide(), benchmark()
    dec["name"] = dec["ticker"].map(securities()["name"])
    dec["delta"] = dec["weight_after"] - dec["weight_before"]
    dec["price_at_decision"] = [px[t].asof(d) for d, t in zip(dec["decision_date"], dec["ticker"])]
    dec["return_since"] = px.iloc[-1][dec["ticker"]].to_numpy() / dec["price_at_decision"] - 1
    dec["bench_since"] = bench.iloc[-1] / dec["decision_date"].map(bench.asof) - 1
    dec["excess_since"] = dec["return_since"] - dec["bench_since"]
    dec["value_added"] = np.where(dec["action"].isin(BUY), 1, -1) * dec["excess_since"]
    dec["worked"] = dec["value_added"] > 0
    return dec.sort_values(["decision_date", "ticker"], ignore_index=True)


def book_around(d: pd.Timestamp) -> pd.DataFrame:
    """Weights just before and after a decision, both valued at that day's close."""
    q, px = quantities(), prices_wide()
    prev = q.index[q.index < d][-1]
    p = px.loc[d].reindex(q.columns)
    nav_d = nav().at[d, "nav"]
    book = pd.DataFrame({"before": q.loc[prev] * p / nav_d, "after": q.loc[d] * p / nav_d})
    book = book[(book["before"] > 0) | (book["after"] > 0)]
    book.loc["CASH"] = [1 - book["before"].sum(), 1 - book["after"].sum()]
    book["change"] = book["after"] - book["before"]
    return book


def sector_weights(weights: pd.Series) -> pd.Series:
    return weights.groupby(securities()["sector"].reindex(weights.index)).sum()


def benchmark_sector_weights() -> pd.Series:
    return load("benchmark_sectors").set_index("sector")["weight"]


def active_sectors(weights: pd.Series | None = None) -> pd.DataFrame:
    weights = holdings()["weight"] if weights is None else weights
    df = pd.DataFrame({"portfolio": sector_weights(weights), "benchmark": benchmark_sector_weights()}).fillna(0.0)
    df["active"] = df["portfolio"] - df["benchmark"]
    return df.sort_values("active")


def alt_signals() -> pd.DataFrame:
    """Latest 4-week YoY per metric, and the change against the prior 13 weeks, per ticker."""
    df = load("alt_data").sort_values("week")
    g = df.groupby(["ticker", "metric"])["yoy"]
    latest = g.apply(lambda s: s.iloc[-4:].mean()).unstack()
    prior = g.apply(lambda s: s.iloc[-17:-4].mean()).unstack()
    out = latest.copy()
    out["momentum"] = (latest - prior).mean(axis=1)
    out["signal"] = np.select([out["momentum"] > 0.015, out["momentum"] < -0.015], ["Accelerating", "Decelerating"], "Stable")
    out["name"] = out.index.map(securities()["name"])
    w = holdings()["weight"]
    out["weight"] = w.reindex(out.index).fillna(0.0)
    return out.sort_values("momentum", ascending=False)


def pb_leverage() -> pd.DataFrame:
    return load("pb_leverage").set_index("week").sort_index()


def pb_sectors() -> pd.DataFrame:
    s = load("pb_sectors").set_index("sector")
    s["active"] = active_sectors()["active"].reindex(s.index).fillna(0.0)
    return s.sort_values("percentile_3y", ascending=False)


def pb_flows() -> pd.DataFrame:
    f = load("pb_sector_flows").pivot(index="sector", columns="week", values="flow_z").sort_index(axis=1)
    return f.iloc[:, -12:]


def crowding() -> pd.DataFrame:
    c = load("pb_crowding").set_index("ticker")
    sec = securities()
    w = holdings()["weight"]
    c["name"] = sec["name"].reindex(c.index)
    c["sector"] = sec["sector"].reindex(c.index)
    c["weight"] = w.reindex(c.index).fillna(0.0)
    c["held"] = c["weight"] > 0
    c["crowded"] = c["crowding_pct"] >= config.CROWDED_PCT
    return c.sort_values(["held", "crowding_pct"], ascending=[False, False])


def suggestions() -> pd.DataFrame:
    """Ideas from the latest day's agent run, with current weights and signal support counted."""
    s = load("agent_suggestions")
    s = s[s["generated_at"].dt.normalize() == s["generated_at"].max().normalize()].copy()
    sec, w = securities(), holdings()["weight"]
    s["name"] = s["ticker"].map(sec["name"])
    s["sector"] = s["ticker"].map(sec["sector"])
    s["current_weight"] = s["ticker"].map(w).fillna(0.0)
    s["change"] = s["target_weight"] - s["current_weight"]
    s["points"] = s["rationale"].str.split(r"\s*\|\s*")
    direction = np.where(s["action"].isin(BUY), 1, -1)
    sig = s[list(SIGNALS)].mul(direction, axis=0)
    s["support"] = (sig > 0).sum(axis=1)
    s["against"] = (sig < 0).sum(axis=1)
    return s.sort_values("confidence", ascending=False, ignore_index=True)


def pre_trade_checks(target: pd.Series) -> list[dict]:
    """Pro Forma limit checks on a ticker -> weight series."""
    lim = config.LIMITS
    held = target[target > 0]
    cash = 1 - target.sum()
    active = active_sectors(held)["active"]
    worst_sector = active.abs().idxmax()
    top = held.idxmax() if len(held) else "-"
    return [
        {"label": "Largest position", "value": f"{top} {held.max():.1%}" if len(held) else "-",
         "limit": f"max {lim['max_position']:.0%}", "ok": held.max() <= lim["max_position"] if len(held) else True},
        {"label": "Cash", "value": f"{cash:.1%}", "limit": f"{lim['min_cash']:.0%} to {lim['max_cash']:.0%}",
         "ok": lim["min_cash"] <= cash <= lim["max_cash"]},
        {"label": "Sector vs benchmark", "value": f"{worst_sector} {active[worst_sector] * 100:+.1f} pp",
         "limit": f"within ±{lim['max_sector_active'] * 100:.0f} pp", "ok": active.abs().max() <= lim["max_sector_active"]},
        {"label": "Positions", "value": f"{len(held)}", "limit": f"{lim['min_positions']} to {lim['max_positions']}",
         "ok": lim["min_positions"] <= len(held) <= lim["max_positions"]},
    ]
