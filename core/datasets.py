"""Data contracts: every dataset the app reads, with its columns, types and checks.

The loader, the validator and the CSV templates are all driven by these specs.
docs/DATA_HANDBOOK.md explains them for the people preparing the files.

Units: weights, returns, shares of NAV and leverage are decimals (0.05 = 5%,
3.0 = 300% gross). Percentiles are 0-100.
"""

from dataclasses import dataclass

SECTORS = (
    "Info Tech", "Comm Services", "Cons Disc", "Cons Staples", "Energy", "Financials",
    "Health Care", "Industrials", "Materials", "Real Estate", "Utilities",
)
ACTIONS = ("Initiate", "Add", "Trim", "Exit")
ALT_METRICS = ("Card spend", "App MAU", "Web visits")
SIGNALS = ("sig_alt_data", "sig_pb_positioning", "sig_momentum", "sig_revisions", "sig_valuation")
EVENT_TYPES = ("Earnings", "Investor day", "Product launch", "Regulatory", "Index change", "Conference",
               "Lock-up expiry", "Macro")
IMPORTANCE = ("High", "Medium", "Low")
TIMINGS = ("Before open", "During market", "After close")


@dataclass(frozen=True)
class Col:
    name: str
    kind: str  # str | float | int | date | datetime
    required: bool = True
    min: float | None = None
    max: float | None = None
    choices: tuple[str, ...] | None = None
    note: str = ""


@dataclass(frozen=True)
class Dataset:
    name: str
    title: str
    frequency: str
    key: tuple[str, ...]
    columns: tuple[Col, ...]
    used_by: tuple[str, ...]


DATASETS = {d.name: d for d in [
    Dataset(
        "securities", "Security master", "On change", ("ticker",),
        (
            Col("ticker", "str", note="Identifier used across every dataset"),
            Col("name", "str"),
            Col("sector", "str", choices=SECTORS, note="GICS sector, short name"),
            Col("beta", "float", required=False, min=-1, max=4, note="Computed from 1y daily returns if blank"),
        ),
        ("All pages",),
    ),
    Dataset(
        "prices", "Daily closing prices", "Daily, after close", ("date", "ticker"),
        (
            Col("date", "date"),
            Col("ticker", "str"),
            Col("close", "float", min=0, note="Adjusted for splits and dividends, in USD"),
        ),
        ("Live Portfolio", "Decision Date", "Pro Forma", "Slides & Charts"),
    ),
    Dataset(
        "benchmark", "Benchmark index level", "Daily, after close", ("date",),
        (
            Col("date", "date"),
            Col("level", "float", min=0, note="Total-return index level"),
        ),
        ("Live Portfolio", "Decision Date"),
    ),
    Dataset(
        "benchmark_sectors", "Benchmark sector weights", "Monthly", ("sector",),
        (
            Col("sector", "str", choices=SECTORS),
            Col("weight", "float", min=0, max=1),
        ),
        ("Live Portfolio", "Pro Forma"),
    ),
    Dataset(
        "positions", "End-of-day positions", "Daily, after close", ("date", "ticker"),
        (
            Col("date", "date"),
            Col("ticker", "str"),
            Col("quantity", "float", min=0, note="Shares held at the close; long-only book"),
            Col("avg_cost", "float", required=False, min=0, note="Average cost per share, USD"),
        ),
        ("Live Portfolio", "Decision Date", "Pro Forma", "Agent Suggestions"),
    ),
    Dataset(
        "nav", "Daily NAV and cash", "Daily, after close", ("date",),
        (
            Col("date", "date"),
            Col("nav", "float", min=0, note="Total NAV in USD, including cash"),
            Col("cash", "float", note="Cash balance in USD"),
            Col("flow", "float", required=False, note="Net subscription (+) or redemption (-) that day, USD"),
        ),
        ("Live Portfolio", "Decision Date", "Pro Forma"),
    ),
    Dataset(
        "decisions", "Investment-committee decisions", "Per meeting", ("decision_date", "ticker"),
        (
            Col("decision_date", "date"),
            Col("ticker", "str"),
            Col("action", "str", choices=ACTIONS),
            Col("weight_before", "float", min=0, max=1),
            Col("weight_after", "float", min=0, max=1),
            Col("rationale", "str", note="One sentence on why"),
            Col("decided_by", "str", required=False),
        ),
        ("Decision Date",),
    ),
    Dataset(
        "agent_suggestions", "Agent trade suggestions", "Each agent run", ("id",),
        (
            Col("id", "str"),
            Col("generated_at", "datetime"),
            Col("ticker", "str"),
            Col("action", "str", choices=ACTIONS),
            Col("target_weight", "float", min=0, max=1),
            Col("confidence", "float", min=0, max=1),
            Col("horizon", "str", note="Free text, e.g. 3-6 months"),
            *(Col(s, "int", min=-1, max=1, note="+1 bullish, 0 neutral, -1 bearish") for s in SIGNALS),
            Col("rationale", "str", note="Bullet points separated by ' | '"),
        ),
        ("Agent Suggestions", "Pro Forma", "Presentation"),
    ),
    Dataset(
        "alt_data", "Alternative data, YoY growth", "Weekly", ("week", "ticker", "metric"),
        (
            Col("week", "date", note="Week-ending date"),
            Col("ticker", "str"),
            Col("metric", "str", choices=ALT_METRICS),
            Col("yoy", "float", min=-1, max=10, note="Year-over-year growth, decimal"),
        ),
        ("Alternative Data", "Live Portfolio", "Slides & Charts"),
    ),
    Dataset(
        "pb_leverage", "Hedge-fund leverage (PB)", "Weekly", ("week",),
        (
            Col("week", "date"),
            Col("gross", "float", min=0, max=10, note="Gross leverage, 3.0 = 300%"),
            Col("net", "float", min=-2, max=5, note="Net leverage, 0.75 = 75%"),
        ),
        ("Prime Broker Positioning", "Slides & Charts"),
    ),
    Dataset(
        "pb_sectors", "Hedge-fund sector positioning (PB)", "Weekly", ("sector",),
        (
            Col("as_of", "date"),
            Col("sector", "str", choices=SECTORS),
            Col("net_share", "float", min=-1, max=1, note="Sector's share of HF net exposure"),
            Col("percentile_3y", "float", min=0, max=100, note="Net exposure vs its own 3-year history"),
            Col("change_4w", "float", required=False, note="4-week change in net_share"),
        ),
        ("Prime Broker Positioning", "Slides & Charts"),
    ),
    Dataset(
        "pb_sector_flows", "Hedge-fund sector flows (PB)", "Weekly", ("week", "sector"),
        (
            Col("week", "date"),
            Col("sector", "str", choices=SECTORS),
            Col("flow_z", "float", min=-10, max=10, note="Net buying z-score vs 1-year history"),
        ),
        ("Prime Broker Positioning", "Slides & Charts"),
    ),
    Dataset(
        "pb_crowding", "Single-stock crowding (PB)", "Weekly", ("ticker",),
        (
            Col("as_of", "date"),
            Col("ticker", "str"),
            Col("crowding_pct", "float", min=0, max=100, note="HF long exposure vs 3-year history"),
            Col("short_interest", "float", min=0, max=1, note="Share of float sold short"),
            Col("days_to_cover", "float", min=0),
            Col("flow_z", "float", required=False, min=-10, max=10, note="Week-over-week net buying z-score"),
        ),
        ("Prime Broker Positioning", "Live Portfolio"),
    ),
    Dataset(
        "catalysts", "Catalyst calendar", "Daily", ("date", "ticker", "event_type"),
        (
            Col("date", "date", note="Event date"),
            Col("ticker", "str", required=False, note="Blank for market-wide events such as FOMC"),
            Col("event_type", "str", choices=EVENT_TYPES),
            Col("title", "str", note="Short description, e.g. Q3 earnings"),
            Col("status", "str", choices=("Confirmed", "Estimated")),
            Col("importance", "str", choices=IMPORTANCE),
            Col("timing", "str", required=False, choices=TIMINGS),
            Col("note", "str", required=False, note="What to watch"),
            Col("source", "str", required=False),
        ),
        ("Catalysts", "Live Portfolio", "Pro Forma", "Agent Suggestions", "Slides & Charts"),
    ),
]}
