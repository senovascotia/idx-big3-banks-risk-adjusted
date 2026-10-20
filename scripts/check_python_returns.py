"""Validate the SQL return views against an independent pandas calculation (metrics M1, M2, M5).

Reads only. Prints PASS or FAIL for each check and exits with status 1 if any check fails.

Usage (project root, virtual environment active):
    python -I scripts/check_python_returns.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db_access

FIRST_RETURN_DAY = pd.Timestamp("2021-01-04")
PRIOR_CLOSE_DAY = pd.Timestamp("2020-12-30")
EXPECTED_DAYS = 1381
REGIME_DAYS = {"R1": 399, "R2": 499, "R3": 393, "Stub": 90}
RET_TOL = 1e-12
RF_TOL = 1e-15
CUM_TOL = 1e-9

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def main():
    with db_access.connect() as conn:
        prices = db_access.load_prices(conn)
        sql = db_access.load_excess_returns(conn)

    close = db_access.to_wide(prices, "close")
    adj = db_access.to_wide(prices, "adj_close")
    ret_close_py = close.pct_change().loc[FIRST_RETURN_DAY:]
    ret_adj_py = adj.pct_change().loc[FIRST_RETURN_DAY:]

    sql_close = db_access.to_wide(sql, "ret_close")
    sql_adj = db_access.to_wide(sql, "ret_adj")

    check("same tickers in SQL view and prices", list(sql_close.columns) == list(ret_close_py.columns),
          ", ".join(sql_close.columns))
    check("same return dates in SQL view and pandas", sql_close.index.equals(ret_close_py.index),
          f"{len(sql_close)} vs {len(ret_close_py)}")
    check(f"{EXPECTED_DAYS} return days per ticker", (sql_close.notna().sum() == EXPECTED_DAYS).all())
    check("no missing returns in pandas", not ret_close_py.isna().any().any())

    d_close = (sql_close - ret_close_py).abs().max().max()
    d_adj = (sql_adj - ret_adj_py).abs().max().max()
    check("M1 ret_close: SQL equals pandas", d_close < RET_TOL, f"max abs diff {d_close:.2e}")
    check("M1 ret_adj: SQL equals pandas", d_adj < RET_TOL, f"max abs diff {d_adj:.2e}")

    cum_py = (1 + ret_close_py).prod() - 1
    cum_px = close.loc[close.index.max()] / close.loc[PRIOR_CLOSE_DAY] - 1
    d_cum = (cum_py - cum_px).abs().max()
    check("M2 cumulative return: compounded returns equal price ratio", d_cum < CUM_TOL,
          f"max abs diff {d_cum:.2e}")
    print("      cumulative price return:", {t: round(float(v), 6) for t, v in cum_py.items()})

    rf_py = sql["rate_pct"] / 100 / 252
    d_rf = (sql["rf_daily"] - rf_py).abs().max()
    check("M5 rf_daily equals rate_pct / 100 / 252", d_rf < RF_TOL, f"max abs diff {d_rf:.2e}")
    check("M5 no missing risk-free rate", not sql["rf_daily"].isna().any())

    ex_py = sql["ret_close"] - rf_py
    d_ex = (sql["excess_close"] - ex_py).abs().max()
    check("M5 excess_close equals ret_close minus rf", d_ex < RET_TOL, f"max abs diff {d_ex:.2e}")

    counts = sql.groupby(["ticker", "regime"]).size().unstack()
    ok = all((counts[r] == n).all() for r, n in REGIME_DAYS.items()) and sum(REGIME_DAYS.values()) == EXPECTED_DAYS
    check("regime day counts per ticker", ok, str(REGIME_DAYS))

    rf_wide = db_access.to_wide(sql, "rf_daily")
    check("risk-free rate identical across tickers on each date", (rf_wide.nunique(axis=1) == 1).all())

    n_fail = results.count(False)
    print(f"\n{len(results) - n_fail} passed, {n_fail} failed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
