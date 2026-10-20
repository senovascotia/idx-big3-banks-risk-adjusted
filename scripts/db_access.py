"""Read-only access to the project database for the Python analysis.

Connection settings come from the environment: PGHOST (default localhost), PGPORT
(default 5432), PGDATABASE (default idx_bank_risk), PGUSER, PGPASSWORD. If PGUSER or
PGPASSWORD is missing the script asks for it at the terminal, so no secret is stored
in a file. Nothing is written to the database.
"""
import getpass
import os

import pandas as pd
import psycopg


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


def _query(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=cols)
    if "trade_date" in df.columns:
        df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df


def load_prices(conn):
    """core.price_daily: ticker, trade_date, close, adj_close (all rows, including 2020-12)."""
    return _query(conn, """
        SELECT ticker, trade_date, close::float8 AS close, adj_close::float8 AS adj_close
        FROM core.price_daily
        ORDER BY ticker, trade_date""")


def load_excess_returns(conn):
    """analytics.excess_return_daily: returns, daily risk-free rate, excess returns and regime."""
    return _query(conn, """
        SELECT ticker, trade_date, regime, ret_close, ret_adj, rate_pct::float8 AS rate_pct,
               rf_daily, excess_close, excess_adj
        FROM analytics.excess_return_daily
        ORDER BY ticker, trade_date""")


def load_capm_sql(conn):
    """CAPM computed in SQL (regr_slope, regr_intercept, regr_r2) for each bank, per regime and Full.

    Independent of the Python regression: used only to cross-check it. Excess returns are the
    close-based series from analytics.excess_return_daily; the market is the IHSG on the same date.
    """
    return _query(conn, """
        SELECT b.ticker, COALESCE(b.regime::text, 'Full') AS period, count(*)::int AS n,
               regr_slope(b.excess_close::float8, m.excess_close::float8) AS beta,
               regr_intercept(b.excess_close::float8, m.excess_close::float8) AS alpha,
               regr_r2(b.excess_close::float8, m.excess_close::float8) AS r2
        FROM analytics.excess_return_daily b
        JOIN analytics.excess_return_daily m ON m.trade_date = b.trade_date AND m.ticker = 'IHSG'
        WHERE b.ticker <> 'IHSG'
        GROUP BY GROUPING SETS ((b.ticker, b.regime), (b.ticker))
        ORDER BY b.ticker, period""")


def load_metrics_sql(conn):
    """M2, M4 and M6 computed in SQL per ticker and period (Full, R1, R2, R3, Stub).

    Independent of metrics.py: cumulative return as exp(sum(ln(1 + r))) - 1, annualized volatility
    as stddev_samp * sqrt(252), annualized Sharpe from the close-based excess returns.
    """
    return _query(conn, """
        SELECT ticker, COALESCE(regime::text, 'Full') AS period, count(*)::int AS n,
               exp(sum(ln(1 + ret_close::float8))) - 1 AS cum_return,
               stddev_samp(ret_close::float8) * sqrt(252) AS ann_vol,
               avg(excess_close::float8) / stddev_samp(excess_close::float8) * sqrt(252) AS sharpe
        FROM analytics.excess_return_daily
        GROUP BY GROUPING SETS ((ticker, regime), (ticker))
        ORDER BY ticker, period""")


def load_mdd_sql(conn):
    """M9 maximum drawdown in SQL (window max) per ticker and period (Full, R1, R2, R3, Stub).

    Each regime's price path is its return days plus the close before the first one, and the
    running maximum starts at that close. The Full path is every row of core.price_daily.
    """
    return _query(conn, """
        WITH px AS (
            SELECT ticker, trade_date, close::float8 AS close,
                   lead(trade_date) OVER (PARTITION BY ticker ORDER BY trade_date) AS next_date
            FROM core.price_daily
        ), regime_path AS (
            SELECT px.ticker, r.regime::text AS period, px.trade_date, px.close
            FROM px JOIN analytics.excess_return_daily r
              ON r.ticker = px.ticker AND (r.trade_date = px.trade_date OR r.trade_date = px.next_date)
            GROUP BY px.ticker, r.regime, px.trade_date, px.close
        ), path AS (
            SELECT ticker, period, trade_date, close FROM regime_path
            UNION ALL
            SELECT ticker, 'Full', trade_date, close FROM px
        ), dd AS (
            SELECT ticker, period, trade_date,
                   close / max(close) OVER (PARTITION BY ticker, period ORDER BY trade_date
                                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) - 1 AS drawdown
            FROM path
        )
        SELECT ticker, period, min(drawdown) AS mdd FROM dd GROUP BY ticker, period ORDER BY ticker, period""")


def to_wide(df, column):
    """Dates down the rows, one column per ticker, so instruments stay aligned by date."""
    return df.pivot(index="trade_date", columns="ticker", values=column).sort_index()
