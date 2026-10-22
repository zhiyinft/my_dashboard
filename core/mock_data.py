"""Deterministic mock datasets, shaped exactly like the live data contracts.

Each public function returns one dataset from core/datasets.py. Tickers are real
for readability; every price, position and signal is synthetic.
"""

from functools import lru_cache

import numpy as np
import pandas as pd

SEED = 23
NAV_START = 100_000_000
N_DAYS = 520
AS_OF = pd.Timestamp.today().normalize() - pd.offsets.BDay(1)

UNIVERSE = pd.DataFrame(
    [
        ("NVDA", "NVIDIA", "Info Tech", 182.0, 1.6),
        ("MSFT", "Microsoft", "Info Tech", 515.0, 1.0),
        ("AAPL", "Apple", "Info Tech", 248.0, 1.1),
        ("TSM", "TSMC", "Info Tech", 290.0, 1.3),
        ("ASML", "ASML", "Info Tech", 960.0, 1.3),
        ("AVGO", "Broadcom", "Info Tech", 345.0, 1.4),
        ("CRM", "Salesforce", "Info Tech", 255.0, 1.1),
        ("ADBE", "Adobe", "Info Tech", 350.0, 1.1),
        ("AMZN", "Amazon", "Cons Disc", 222.0, 1.2),
        ("MELI", "MercadoLibre", "Cons Disc", 2310.0, 1.3),
        ("NKE", "Nike", "Cons Disc", 70.0, 1.0),
        ("GOOGL", "Alphabet", "Comm Services", 252.0, 1.1),
        ("META", "Meta Platforms", "Comm Services", 715.0, 1.3),
        ("NFLX", "Netflix", "Comm Services", 1210.0, 1.2),
        ("JPM", "JPMorgan Chase", "Financials", 302.0, 1.0),
        ("V", "Visa", "Financials", 345.0, 0.9),
        ("LLY", "Eli Lilly", "Health Care", 820.0, 0.7),
        ("UNH", "UnitedHealth", "Health Care", 352.0, 0.6),
        ("ISRG", "Intuitive Surgical", "Health Care", 455.0, 1.1),
        ("PFE", "Pfizer", "Health Care", 25.0, 0.6),
        ("XOM", "Exxon Mobil", "Energy", 114.0, 0.8),
        ("COST", "Costco", "Cons Staples", 935.0, 0.7),
        ("GE", "GE Aerospace", "Industrials", 298.0, 1.1),
        ("UBER", "Uber", "Industrials", 98.0, 1.3),
        ("BA", "Boeing", "Industrials", 215.0, 1.2),
    ],
    columns=["ticker", "name", "sector", "last", "beta"],
).set_index("ticker")

CURRENT_WEIGHTS = {
    "NVDA": 0.085, "MSFT": 0.080, "AMZN": 0.070, "GOOGL": 0.065, "META": 0.060,
    "TSM": 0.060, "AVGO": 0.055, "LLY": 0.055, "JPM": 0.050, "V": 0.050,
    "NFLX": 0.045, "AAPL": 0.045, "ASML": 0.040, "COST": 0.040, "GE": 0.040,
    "ISRG": 0.035, "MELI": 0.035, "XOM": 0.030, "UBER": 0.030,
}

BENCHMARK_SECTORS = {
    "Info Tech": 0.26, "Financials": 0.17, "Industrials": 0.11, "Cons Disc": 0.11,
    "Health Care": 0.10, "Comm Services": 0.08, "Cons Staples": 0.06, "Energy": 0.04,
    "Materials": 0.04, "Utilities": 0.03,
}

RATIONALES = {
    "Initiate": [
        "Alt data inflecting: card spend +{x}% YoY, ahead of consensus",
        "Valuation reset after de-rating; entry at {pe}x forward P/E",
        "PB data shows hedge funds underweight, room to re-rate",
    ],
    "Add": [
        "Estimate revisions trending up ({n} upgrades in 30 days)",
        "App engagement accelerating for {n} straight weeks",
        "Pullback to the 50-day average after a strong print",
    ],
    "Trim": [
        "Position above risk limit after rally; locking in gains",
        "Crowding elevated: PB long exposure at {p}th percentile",
        "Momentum fading; web traffic decelerating",
    ],
    "Exit": [
        "Thesis broken: guidance cut on weak demand",
        "Better risk/reward elsewhere; funding a new idea",
        "Regulatory overhang not priced in",
    ],
}


@lru_cache
def _prices_wide() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range(end=AS_OF, periods=N_DAYS)
    market = rng.normal(0.0004, 0.009, len(dates))
    rets = {}
    for t, row in UNIVERSE.iterrows():
        alpha = rng.normal(0.0002, 0.0004)
        idio = rng.uniform(0.010, 0.020)
        rets[t] = row["beta"] * market + rng.normal(alpha, idio, len(dates))
    r = pd.DataFrame(rets, index=dates)
    r.iloc[0] = 0.0
    log_px = r.cumsum()
    px = np.exp(log_px - log_px.iloc[-1]) * UNIVERSE["last"]
    market[0] = 0.0
    px["BENCH"] = 100 * np.exp(np.cumsum(market))
    return px


def _decision_dates() -> list[pd.Timestamp]:
    months = pd.date_range(end=AS_OF, periods=10, freq="MS")
    dates = [m + pd.offsets.BDay(6) for m in months]
    return [d for d in dates if d < AS_OF][-9:]


@lru_cache
def _decision_plan() -> tuple[pd.DataFrame, pd.Series]:
    """Committee trades, generated backwards from today's target book.

    Returns (trades, starting weights). Walking back from CURRENT_WEIGHTS keeps
    the history consistent with today's holdings.
    """
    rng = np.random.default_rng(SEED + 1)
    tickers = list(UNIVERSE.index)
    w = pd.Series(0.0, index=tickers + ["CASH"])
    for t, v in CURRENT_WEIGHTS.items():
        w[t] = v
    w["CASH"] = 1 - sum(CURRENT_WEIGHTS.values())

    trades = []
    for d in reversed(_decision_dates()):
        used = set()
        for _ in range(int(rng.integers(2, 5))):
            if w["CASH"] < 0.03:
                action = rng.choice(["Add", "Initiate"])
            elif w["CASH"] > 0.07:
                action = rng.choice(["Trim", "Exit"])
            else:
                action = rng.choice(["Add", "Trim", "Initiate", "Exit"], p=[0.35, 0.3, 0.175, 0.175])
            held = [t for t in tickers if w[t] > 0 and t not in used]
            unheld = [t for t in tickers if w[t] == 0 and t not in used]
            if action == "Initiate":
                pool = [t for t in held if w[t] <= 0.045]
                if not pool:
                    continue
                t = str(rng.choice(pool))
                after, before = w[t], 0.0
            elif action == "Exit":
                if not unheld:
                    continue
                t = str(rng.choice(unheld))
                after, before = 0.0, round(rng.uniform(0.02, 0.035), 3)
            elif action == "Add":
                pool = [t for t in held if w[t] >= 0.025]
                if not pool:
                    continue
                t = str(rng.choice(pool))
                after = w[t]
                before = round(after - rng.uniform(0.005, 0.015), 3)
            else:
                t = str(rng.choice(held))
                after = w[t]
                before = round(after + rng.uniform(0.005, 0.015), 3)
            used.add(t)
            w[t] = before
            w["CASH"] += after - before
            template = rng.choice(RATIONALES[str(action)])
            trades.append({
                "decision_date": d, "ticker": t, "action": str(action),
                "weight_before": before, "weight_after": after,
                "rationale": template.format(
                    x=int(rng.integers(8, 25)), pe=int(rng.integers(14, 28)),
                    n=int(rng.integers(3, 9)), p=int(rng.integers(85, 99)),
                ),
                "decided_by": "Investment Committee",
            })
    trades = pd.DataFrame(trades).sort_values(["decision_date", "ticker"], ignore_index=True)
    return trades, w


@lru_cache
def _book() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Simulate the book forward through the committee trades.

    Returns (positions, nav, decisions). Shares are held constant between
    decisions, so weights drift with prices as they would in a real book;
    each decision's weight_before is the drifted weight on the day.
    """
    rng = np.random.default_rng(SEED + 7)
    px = _prices_wide()
    trades, w0 = _decision_plan()
    by_date = {d: g for d, g in trades.groupby("decision_date")}

    p0 = px.iloc[0]
    shares = {t: round(w0[t] * NAV_START / p0[t]) for t in w0.index if t != "CASH" and w0[t] > 0}
    cost = {t: p0[t] * rng.uniform(0.6, 1.05) for t in shares}
    cash = NAV_START - sum(q * p0[t] for t, q in shares.items())

    pos_rows, nav_rows, decided = [], [], []
    for d in px.index:
        p = px.loc[d]
        if d in by_date:
            nav_d = cash + sum(q * p[t] for t, q in shares.items())
            for tr in by_date[d].itertuples():
                t = tr.ticker
                held = shares.get(t, 0)
                target = round(tr.weight_after * nav_d / p[t])
                delta = target - held
                cash -= delta * p[t]
                if delta > 0:
                    cost[t] = (cost.get(t, 0.0) * held + p[t] * delta) / target
                decided.append({**tr._asdict(), "weight_before": round(held * p[t] / nav_d, 4)})
                if target == 0:
                    shares.pop(t, None)
                    cost.pop(t, None)
                else:
                    shares[t] = target
        nav_d = cash + sum(q * p[t] for t, q in shares.items())
        for t, q in shares.items():
            pos_rows.append((d, t, float(q), round(cost[t], 4)))
        nav_rows.append((d, nav_d, cash, 0.0))

    positions = pd.DataFrame(pos_rows, columns=["date", "ticker", "quantity", "avg_cost"])
    nav = pd.DataFrame(nav_rows, columns=["date", "nav", "cash", "flow"])
    decisions = pd.DataFrame(decided).drop(columns="Index")
    return positions, nav, decisions


def securities() -> pd.DataFrame:
    return UNIVERSE.reset_index()[["ticker", "name", "sector", "beta"]]


def prices() -> pd.DataFrame:
    px = _prices_wide().drop(columns="BENCH")
    return px.rename_axis("date").reset_index().melt(id_vars="date", var_name="ticker", value_name="close")


def benchmark() -> pd.DataFrame:
    return _prices_wide()["BENCH"].rename("level").rename_axis("date").reset_index()


def benchmark_sectors() -> pd.DataFrame:
    return pd.DataFrame({"sector": list(BENCHMARK_SECTORS), "weight": list(BENCHMARK_SECTORS.values())})


def positions() -> pd.DataFrame:
    return _book()[0]


def nav() -> pd.DataFrame:
    return _book()[1]


def decisions() -> pd.DataFrame:
    return _book()[2]


# Weight changes are relative to the simulated book, so a Trim always lowers the weight.
_SUGGESTIONS = [
    ("S-101", "CRM", "Initiate", 0.025, 0.72, "6-12 months", (1, 1, 0, 1, 1), [
        "Web visits and app MAU both accelerating for 6 straight weeks",
        "Hedge funds hold it at the 22nd percentile of 3y exposure: under-owned",
        "Trades at a 15% discount to its 5-year forward P/E average",
    ]),
    ("S-102", "LLY", "Add", 0.010, 0.69, "3-6 months", (1, 0, 1, 1, -1), [
        "Script data for the GLP-1 franchise running 9pp ahead of consensus",
        "Six upward EPS revisions in the last 30 days",
        "Premium valuation is the main risk; size the add modestly",
    ]),
    ("S-103", "NFLX", "Trim", -0.015, 0.61, "1-3 months", (-1, -1, 0, 0, -1), [
        "App engagement decelerating three quarters in a row",
        "PB long crowding at the 92nd percentile, among the highest in the book",
        "Locks in gains ahead of the next print",
    ]),
    ("S-104", "META", "Trim", -0.010, 0.58, "1-3 months", (0, -1, 1, 0, 0), [
        "Crowded long: 88th percentile of hedge-fund exposure",
        "Capex guide raises margin risk into year end",
    ]),
    ("S-105", "XOM", "Exit", None, 0.55, "3-6 months", (-1, 0, -1, -1, 1), [
        "Card spend at fuel stations decelerating; refining margins rolling over",
        "Funds the CRM initiation without raising gross exposure",
    ]),
    ("S-106", "NVDA", "Add", 0.010, 0.52, "6-12 months", (1, -1, 1, 1, 0), [
        "Hyperscaler capex commentary implies upside to data-center revenue",
        "Crowded and already a top-five position; check the risk limit before adding",
    ]),
    ("S-107", "UNH", "Initiate", 0.020, 0.44, "12+ months", (0, 1, -1, -1, 1), [
        "Deep value after the de-rating; sentiment washed out",
        "Low conviction: revisions still negative, wait for medical-cost trend to turn",
    ]),
]


def agent_suggestions() -> pd.DataFrame:
    run = pd.Timestamp.today().normalize() + pd.Timedelta(hours=7, minutes=30)
    pos, nav_df, _ = _book()
    last = pos[pos["date"] == pos["date"].max()].set_index("ticker")["quantity"]
    weights = last * _prices_wide().iloc[-1][last.index] / nav_df["nav"].iloc[-1]
    rows = []
    for sid, t, action, change, conf, horizon, sigs, rationale in _SUGGESTIONS:
        target = 0.0 if change is None else round((weights.get(t, 0.0) + change) / 0.0025) * 0.0025
        rows.append({
            "id": sid, "generated_at": run, "ticker": t, "action": action, "target_weight": round(target, 4),
            "confidence": conf, "horizon": horizon,
            **dict(zip(["sig_alt_data", "sig_pb_positioning", "sig_momentum", "sig_revisions", "sig_valuation"], sigs)),
            "rationale": " | ".join(rationale),
        })
    return pd.DataFrame(rows)


ALT_METRICS = ["Card spend", "App MAU", "Web visits"]
ALT_COVERAGE = ["AMZN", "MELI", "GOOGL", "META", "NFLX", "AAPL", "COST", "NKE", "UBER", "V", "CRM", "ADBE", "LLY", "XOM"]
ALT_BIAS = {"CRM": 0.07, "LLY": 0.06, "AMZN": 0.02, "NFLX": -0.07, "XOM": -0.05, "NKE": -0.05}


def alt_data() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 2)
    weeks = pd.date_range(end=AS_OF, periods=104, freq="W-FRI")
    ramp = np.r_[np.zeros(len(weeks) - 13), np.linspace(0, 1, 13)]
    rows = []
    for t in ALT_COVERAGE:
        base = rng.normal(0.08, 0.06)
        for metric in ALT_METRICS:
            shock = np.zeros(len(weeks))
            for i in range(1, len(weeks)):
                shock[i] = 0.92 * shock[i - 1] + rng.normal(0, 0.012)
            yoy = base + rng.normal(0, 0.02) + shock + rng.normal(0, 0.006, len(weeks))
            yoy = yoy + ALT_BIAS.get(t, 0.0) * ramp
            rows.append(pd.DataFrame({"week": weeks, "ticker": t, "metric": metric, "yoy": yoy}))
    return pd.concat(rows, ignore_index=True)


PB_SECTORS = ["Info Tech", "Comm Services", "Cons Disc", "Financials", "Health Care",
              "Industrials", "Cons Staples", "Energy", "Materials", "Utilities"]


def pb_leverage() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 3)
    weeks = pd.date_range(end=AS_OF, periods=156, freq="W-FRI")
    g = np.zeros(len(weeks))
    n = np.zeros(len(weeks))
    for i in range(1, len(weeks)):
        g[i] = 0.95 * g[i - 1] + rng.normal(0, 2.2)
        n[i] = 0.93 * n[i - 1] + rng.normal(0, 1.4)
    trend = np.linspace(0, 1, len(weeks)) ** 2
    return pd.DataFrame({"week": weeks, "gross": (278 + g + 18 * trend) / 100, "net": (71 + n + 6 * trend) / 100})


def pb_sectors() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 4)
    pct = {"Info Tech": 91, "Comm Services": 84, "Cons Disc": 47, "Financials": 63, "Health Care": 18,
           "Industrials": 72, "Cons Staples": 29, "Energy": 12, "Materials": 35, "Utilities": 55}
    share = rng.dirichlet(np.ones(len(PB_SECTORS)) * 3)
    return pd.DataFrame({
        "as_of": AS_OF, "sector": PB_SECTORS, "net_share": share,
        "percentile_3y": [float(pct[s]) for s in PB_SECTORS],
        "change_4w": rng.normal(0, 0.012, len(PB_SECTORS)),
    })


def pb_sector_flows() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 5)
    weeks = pd.date_range(end=AS_OF, periods=12, freq="W-FRI")
    z = np.zeros((len(PB_SECTORS), len(weeks)))
    for j in range(len(weeks)):
        prev = z[:, j - 1] if j else 0
        z[:, j] = 0.5 * prev + rng.normal(0, 0.9, len(PB_SECTORS))
    wide = pd.DataFrame(z.round(2), index=pd.Index(PB_SECTORS, name="sector"), columns=weeks)
    return wide.rename_axis(columns="week").stack().rename("flow_z").reset_index()[["week", "sector", "flow_z"]]


def pb_crowding() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 6)
    fixed = {"NVDA": 95, "NFLX": 92, "META": 88, "MSFT": 86, "AVGO": 83, "CRM": 22, "UNH": 15, "XOM": 30, "PFE": 9}
    tickers = list(UNIVERSE.index)
    return pd.DataFrame({
        "as_of": AS_OF,
        "ticker": tickers,
        "crowding_pct": [float(fixed.get(t, int(rng.integers(25, 80)))) for t in tickers],
        "short_interest": rng.uniform(0.006, 0.05, len(tickers)),
        "days_to_cover": rng.uniform(0.8, 5.0, len(tickers)),
        "flow_z": rng.normal(0, 1, len(tickers)),
    })


GENERATORS = {
    "securities": securities, "prices": prices, "benchmark": benchmark,
    "benchmark_sectors": benchmark_sectors, "positions": positions, "nav": nav,
    "decisions": decisions, "agent_suggestions": agent_suggestions, "alt_data": alt_data,
    "pb_leverage": pb_leverage, "pb_sectors": pb_sectors, "pb_sector_flows": pb_sector_flows,
    "pb_crowding": pb_crowding,
}
