"""Verify yfinance tickers, date alignment and adjustment conventions before loading.

Read-only with respect to the project: prices are downloaded into memory and
only a text report (and a few small CSV check tables) is written to --out.

Usage:
    python -I scripts/verify_yfinance.py --out <report_dir>
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

SYMBOLS = ["BBCA.JK", "BMRI.JK", "BBRI.JK", "^JKSE"]
START, END = "2020-12-24", "2026-10-01"
MOVE_FLAG = 0.08


def section(title):
    print(f"\n{'=' * 8} {title} {'=' * 8}")


def identity(sym):
    """Check 1: does the ticker resolve to the intended instrument?"""
    try:
        info = yf.Ticker(sym).info
        keep = ("longName", "shortName", "exchange", "fullExchangeName", "currency", "quoteType")
        return {k: info.get(k) for k in keep}
    except Exception as exc:
        return {"error": repr(exc)}


def load(sym):
    df = yf.Ticker(sym).history(start=START, end=END, auto_adjust=False, actions=True)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def structure_checks(sym, df):
    """Check 2: structure, duplicates, missing values, price sanity."""
    out = {
        "rows": len(df),
        "first": df.index.min().date(),
        "last": df.index.max().date(),
        "duplicate_dates": int(df.index.duplicated().sum()),
        "monotonic_increasing": bool(df.index.is_monotonic_increasing),
        "weekend_rows": int((df.index.dayofweek >= 5).sum()),
        "nan_by_col": df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].isna().sum().to_dict(),
        "nonpositive_prices": int((df[["Open", "High", "Low", "Close"]] <= 0).sum().sum()),
        "high_lt_low": int((df["High"] < df["Low"]).sum()),
        "close_outside_hl": int(((df["Close"] > df["High"]) | (df["Close"] < df["Low"])).sum()),
        "zero_volume_days": int((df["Volume"] == 0).sum()),
        "max_calendar_gap_days": int(df.index.to_series().diff().dt.days.max()),
    }
    return out


def alignment_checks(frames):
    """Check 3: do all four series share the same trading dates?"""
    base = frames[SYMBOLS[0]].index
    res = {}
    for sym in SYMBOLS[1:]:
        idx = frames[sym].index
        res[sym] = {
            "only_in_base": [d.date() for d in base.difference(idx)][:10],
            "only_in_this": [d.date() for d in idx.difference(base)][:10],
            "identical_dates": bool(base.equals(idx)),
        }
    return res


def adjustment_checks(sym, df):
    """Check 4: what does 'Adj Close' do? Compare against Close and the dividend log."""
    ratio = df["Adj Close"] / df["Close"]
    divs = df.loc[df["Dividends"] > 0, "Dividends"]
    splits = df.loc[df["Stock Splits"] > 0, "Stock Splits"]
    rows = []
    for d, amt in divs.items():
        i = df.index.get_loc(d)
        if i == 0:
            continue
        p_prev = df["Close"].iloc[i - 1]
        expected = 1 - amt / p_prev
        implied = ratio.iloc[i - 1] / ratio.iloc[i]
        rows.append({"ex_date": d.date(), "dividend": amt, "prev_close": p_prev,
                     "expected_factor": expected, "implied_factor": implied,
                     "abs_diff": abs(implied - expected)})
    div_tbl = pd.DataFrame(rows)
    return {
        "ratio_min": float(ratio.min()), "ratio_max": float(ratio.max()),
        "ratio_first": float(ratio.iloc[0]), "ratio_last": float(ratio.iloc[-1]),
        "adj_equals_close_everywhere": bool(np.allclose(df["Adj Close"], df["Close"])),
        "dividend_events": len(divs),
        "dividends_total": float(divs.sum()) if len(divs) else 0.0,
        "split_events": {str(d.date()): float(v) for d, v in splits.items()},
        "max_abs_factor_diff": float(div_tbl["abs_diff"].max()) if len(div_tbl) else None,
    }, div_tbl


def move_checks(sym, df):
    """Check 5: large moves are listed for investigation (corporate action vs real move vs error)."""
    r_close = df["Close"].pct_change()
    r_adj = df["Adj Close"].pct_change()
    flagged = df.loc[(r_close.abs() > MOVE_FLAG) | (r_adj.abs() > MOVE_FLAG)].copy()
    flagged["ret_close"] = r_close.loc[flagged.index]
    flagged["ret_adj"] = r_adj.loc[flagged.index]
    return flagged[["Close", "Adj Close", "Volume", "Dividends", "Stock Splits", "ret_close", "ret_adj"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="folder for the report and check tables")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200, "display.max_columns", 20)

    print(f"yfinance {yf.__version__}; request {START} -> {END} (exclusive); auto_adjust=False")

    section("1. Ticker identity")
    for s in SYMBOLS:
        print(s, identity(s))

    frames = {s: load(s) for s in SYMBOLS}

    section("2. Structure and sanity checks")
    for s in SYMBOLS:
        print(s, structure_checks(s, frames[s]))

    section("3. Date alignment across the four series")
    for s, r in alignment_checks(frames).items():
        print(f"{SYMBOLS[0]} vs {s}:", r)

    section("4. Adjustment convention (Adj Close vs Close vs dividends/splits)")
    for s in SYMBOLS:
        summary, tbl = adjustment_checks(s, frames[s])
        print(s, summary)
        if len(tbl):
            tbl.to_csv(out / f"dividend_factor_check_{s.replace('^', '')}.csv", index=False)

    section("5. Large daily moves (|return| > 8%), for investigation only")
    for s in SYMBOLS:
        tbl = move_checks(s, frames[s])
        print(f"{s}: {len(tbl)} flagged")
        if len(tbl):
            print(tbl.to_string())
            tbl.to_csv(out / f"large_moves_{s.replace('^', '')}.csv")

    section("6. Trading days per calendar year (2021 onward)")
    cnt = pd.DataFrame({s: frames[s].loc["2021-01-01":].groupby(frames[s].loc["2021-01-01":].index.year).size()
                        for s in SYMBOLS})
    print(cnt)


if __name__ == "__main__":
    sys.exit(main())
