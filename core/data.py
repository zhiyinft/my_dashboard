"""Load each dataset from data/live/ when a file is present, otherwise from mock data.

Command line, run from the project root:

    python -m core.data validate     # check every file in data/live/ against its contract
    python -m core.data templates    # rewrite data/templates/ from the mock data
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from core import mock_data
from core.config import LIVE_DIR, TEMPLATE_DIR
from core.datasets import DATASETS, Dataset


class DataError(ValueError):
    pass


def live_file(name: str):
    for ext in (".parquet", ".csv"):
        path = LIVE_DIR / f"{name}{ext}"
        if path.exists():
            return path
    return None


def source(name: str) -> str:
    return "live" if live_file(name) else "mock"


def _coerce(df: pd.DataFrame, spec: Dataset) -> pd.DataFrame:
    df = df.copy()
    for col in spec.columns:
        if col.name not in df:
            continue
        s = df[col.name]
        if col.kind == "date":
            df[col.name] = pd.to_datetime(s, errors="coerce").dt.normalize()
        elif col.kind == "datetime":
            df[col.name] = pd.to_datetime(s, errors="coerce")
        elif col.kind in ("float", "int"):
            df[col.name] = pd.to_numeric(s, errors="coerce")
        else:
            df[col.name] = s.astype("string").str.strip()
    return df


def problems(raw: pd.DataFrame, spec: Dataset) -> list[str]:
    """Contract violations in one dataset, as readable sentences. Empty means valid."""
    out = []
    missing = [c.name for c in spec.columns if c.required and c.name not in raw]
    if missing:
        return [f"missing required column(s): {', '.join(missing)}"]
    df = _coerce(raw, spec)
    for col in spec.columns:
        if col.name not in df:
            continue
        s, r = df[col.name], raw[col.name]
        unparsed = s.isna() & r.notna() & (r.astype("string").str.strip() != "")
        if unparsed.any():
            out.append(f"{col.name}: {unparsed.sum()} value(s) are not a valid {col.kind}, e.g. {r[unparsed].iloc[0]!r}")
        if col.required and s.isna().any():
            out.append(f"{col.name}: {s.isna().sum()} blank value(s) in a required column")
        if col.min is not None and (s < col.min).any():
            out.append(f"{col.name}: {(s < col.min).sum()} value(s) below {col.min}")
        if col.max is not None and (s > col.max).any():
            out.append(f"{col.name}: {(s > col.max).sum()} value(s) above {col.max}; check units (decimals, not percent)")
        if col.choices is not None:
            bad = s.notna() & ~s.isin(col.choices)
            if bad.any():
                out.append(f"{col.name}: unknown value(s) {sorted(set(s[bad]))[:5]}; allowed: {', '.join(col.choices)}")
    dupes = df.duplicated(list(spec.key)).sum()
    if dupes:
        out.append(f"{dupes} duplicate row(s) for key ({', '.join(spec.key)})")
    return out


def _read(path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


@st.cache_data(show_spinner=False)
def _load(name: str, path: str | None, mtime: float | None) -> pd.DataFrame:
    spec = DATASETS[name]
    if path is None:
        return mock_data.GENERATORS[name]()
    raw = _read(LIVE_DIR / path)
    issues = problems(raw, spec)
    if issues:
        raise DataError(f"data/live/{path} fails its contract:\n- " + "\n- ".join(issues))
    return _coerce(raw, spec)


def load(name: str) -> pd.DataFrame:
    """One dataset as a DataFrame. Cached until its live file (or the mock generator) changes."""
    path = live_file(name)
    if path:
        return _load(name, path.name, path.stat().st_mtime)
    return _load(name, None, Path(mock_data.__file__).stat().st_mtime)


def _cross_checks(frames: dict[str, pd.DataFrame]) -> list[str]:
    out = []
    known = set(frames["securities"]["ticker"]) if "securities" in frames else None
    if known is not None:
        for name, df in frames.items():
            if name != "securities" and "ticker" in df:
                unknown = sorted(set(df["ticker"].dropna()) - known)
                if unknown:
                    out.append(f"{name}: ticker(s) missing from securities: {', '.join(unknown[:8])}")
    if {"positions", "prices"} <= frames.keys():
        priced = frames["prices"].set_index(["date", "ticker"]).index
        unpriced = ~frames["positions"].set_index(["date", "ticker"]).index.isin(priced)
        if unpriced.any():
            out.append(f"positions: {unpriced.sum()} position(s) have no price on that date")
    if {"positions", "nav"} <= frames.keys():
        gap = sorted(set(frames["positions"]["date"]) - set(frames["nav"]["date"]))
        if gap:
            out.append(f"nav: missing for {len(gap)} date(s) that have positions, e.g. {gap[0]:%Y-%m-%d}")
    return out


def validate() -> int:
    print(f"Checking {LIVE_DIR}\n")
    failed, frames = 0, {}
    for name, spec in DATASETS.items():
        path = live_file(name)
        if path is None:
            print(f"  -     {name:<18} not provided, app uses mock data")
            continue
        raw = _read(path)
        issues = problems(raw, spec)
        if issues:
            failed += 1
            print(f"  FAIL  {name:<18} {path.name}, {len(raw):,} rows")
            for i in issues:
                print(f"          - {i}")
        else:
            frames[name] = _coerce(raw, spec)
            print(f"  ok    {name:<18} {path.name}, {len(raw):,} rows")
    cross = _cross_checks(frames)
    if cross:
        print("\nCross-dataset checks:")
        for c in cross:
            print(f"  - {c}")
    print("\nAll provided files pass." if not failed and not cross else "\nFix the issues above, then rerun.")
    return 1 if failed or cross else 0


def write_templates(rows: int = 12) -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    for name, spec in DATASETS.items():
        df = mock_data.GENERATORS[name]()
        time = next((c for c in spec.key if c in ("date", "week")), None)
        if time and len(spec.key) > 1:
            df = df[df[time] == df[time].max()]
        elif time:
            df = df.tail(rows)
        out = df[[c.name for c in spec.columns if c.name in df]].copy()
        for col in spec.columns:
            if col.kind == "date" and col.name in out:
                out[col.name] = pd.to_datetime(out[col.name]).dt.strftime("%Y-%m-%d")
            elif col.kind == "float" and col.name in out:
                out[col.name] = out[col.name].round(6)
        out.to_csv(TEMPLATE_DIR / f"{name}.csv", index=False)
        print(f"wrote data/templates/{name}.csv ({len(out)} rows)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "templates":
        write_templates()
    else:
        sys.exit(validate())
