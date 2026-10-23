"""App-wide settings: where live data lives, the benchmark label, and pre-trade limits."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_DIR = ROOT / "data" / "live"
TEMPLATE_DIR = ROOT / "data" / "templates"

BENCHMARK_NAME = "Benchmark"

# Pro Forma pre-trade checks. Weights are decimals (0.10 = 10%).
LIMITS = {
    "max_position": 0.10,
    "min_cash": 0.01,
    "max_cash": 0.10,
    "max_sector_active": 0.15,
    "min_positions": 15,
    "max_positions": 30,
}

# A holding counts as crowded at or above this PB crowding percentile.
CROWDED_PCT = 85

# Catalysts: Pro Forma warns about trades this many trading days before an earnings
# or high-importance event; Live Portfolio's attention card looks this many days ahead.
EVENT_WARNING_BDAYS = 5
ATTENTION_DAYS = 7
