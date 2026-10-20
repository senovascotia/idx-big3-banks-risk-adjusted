"""Load yfinance prices into PostgreSQL (raw layer first, then core layer).

Connection settings come from the environment: PGHOST (default localhost), PGPORT
(default 5432), PGDATABASE (default idx_bank_risk), PGUSER, PGPASSWORD. If PGUSER or
PGPASSWORD is missing the script asks for it at the terminal, so no secret is stored
in a file. Nothing is written to disk.

The whole run is ONE transaction: if any step fails, nothing is saved.

Usage (project root, virtual environment active):
    python -I scripts/load_prices.py
"""
import getpass
import os
import sys

import pandas as pd
import psycopg
import yfinance as yf

SYMBOLS = ["BBCA.JK", "BMRI.JK", "BBRI.JK", "^JKSE"]
START, END = "2020-12-24", "2026-10-01"
AUTO_ADJUST = False


def connect():
    user = os.environ.get("PGUSER") or input("PostgreSQL user: ")
    password = os.environ.get("PGPASSWORD") or getpass.getpass("PostgreSQL password: ")
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "idx_bank_risk"),
        user=user,
        password=password,
    )


def fetch(symbol):
    df = yf.Ticker(symbol).history(start=START, end=END, auto_adjust=AUTO_ADJUST, actions=True)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def num(value, cast=float):
    """NaN -> None (SQL NULL); otherwise a plain Python number."""
    return None if pd.isna(value) else cast(value)


def to_rows(load_id, symbol, df):
    rows = []
    for day, r in df.iterrows():
        rows.append((
            load_id, symbol, day.date(),
            num(r["Open"]), num(r["High"]), num(r["Low"]), num(r["Close"]), num(r["Adj Close"]),
            num(r["Volume"], int), num(r["Dividends"]), num(r["Stock Splits"]),
        ))
    return rows


INSERT_RAW = """
    INSERT INTO raw.yf_price_daily
        (load_id, source_symbol, trade_date, open, high, low, close, adj_close,
         volume, dividends, stock_splits)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

INSERT_CORE = """
    INSERT INTO core.price_daily
        (ticker, trade_date, open, high, low, close, adj_close, volume,
         dividends, stock_splits, source_load_id)
    SELECT i.ticker, r.trade_date, r.open, r.high, r.low, r.close, r.adj_close, r.volume,
           COALESCE(r.dividends, 0), COALESCE(r.stock_splits, 0), r.load_id
    FROM raw.yf_price_daily AS r
    JOIN ref.instrument AS i ON i.source_symbol = r.source_symbol
"""


def main():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT (SELECT count(*) FROM raw.load_log), (SELECT count(*) FROM core.price_daily)")
        n_log, n_core = cur.fetchone()
        if n_log or n_core:
            sys.exit(f"Refusing to load: raw.load_log has {n_log} rows, core.price_daily has {n_core}. "
                     "Both must be empty. Tell me before deleting anything.")

        for symbol in SYMBOLS:
            df = fetch(symbol)
            cur.execute(
                """INSERT INTO raw.load_log
                       (source, source_version, source_symbol, request_start, request_end,
                        auto_adjust, rows_loaded)
                   VALUES ('yfinance', %s, %s, %s, %s, %s, %s) RETURNING load_id""",
                (yf.__version__, symbol, START, END, AUTO_ADJUST, len(df)),
            )
            load_id = cur.fetchone()[0]
            cur.executemany(INSERT_RAW, to_rows(load_id, symbol, df))
            print(f"raw  {symbol:8s} load_id={load_id} rows={len(df)}")

        cur.execute(INSERT_CORE)
        print(f"core rows inserted: {cur.rowcount}")

        cur.execute("SELECT count(*) FROM raw.yf_price_daily")
        n_raw = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM core.price_daily")
        n_core = cur.fetchone()[0]
        if n_core != n_raw:
            raise RuntimeError(f"core has {n_core} rows but raw has {n_raw}: the instrument join dropped rows")

        cur.execute("""SELECT ticker, count(*), min(trade_date), max(trade_date)
                       FROM core.price_daily GROUP BY ticker ORDER BY ticker""")
        print("\ncore.price_daily by ticker (ticker, rows, first date, last date):")
        for row in cur.fetchall():
            print("  ", row)
        cur.execute("SELECT count(DISTINCT trade_date) FROM core.price_daily")
        print("distinct trading dates across all tickers:", cur.fetchone()[0])
    print("\nCommitted.")


if __name__ == "__main__":
    main()
