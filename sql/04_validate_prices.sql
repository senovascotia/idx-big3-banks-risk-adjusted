SELECT extract(year FROM trade_date)::int AS yr, ticker, count(*) AS n_rows
FROM core.price_daily
GROUP BY 1, 2
ORDER BY 1, 2;

SELECT trade_date, count(*) AS tickers_present
FROM core.price_daily
GROUP BY trade_date
HAVING count(*) <> (SELECT count(*) FROM ref.instrument)
ORDER BY trade_date;

SELECT ticker, count(*) AS open_outside_range
FROM core.price_daily
WHERE open < low OR open > high
GROUP BY ticker
ORDER BY ticker;

WITH r AS (
    SELECT ticker, trade_date, close, adj_close, dividends,
           close     / lag(close)     OVER w - 1 AS ret_close,
           adj_close / lag(adj_close) OVER w - 1 AS ret_adj
    FROM core.price_daily
    WINDOW w AS (PARTITION BY ticker ORDER BY trade_date)
)
SELECT ticker, trade_date, round(ret_close * 100, 2) AS ret_close_pct,
       round(ret_adj * 100, 2) AS ret_adj_pct, dividends
FROM r
WHERE abs(ret_close) > 0.08 OR abs(ret_adj) > 0.08
ORDER BY ticker, trade_date;

SELECT ticker,
       count(*) FILTER (WHERE dividends > 0)     AS dividend_events,
       sum(dividends)                            AS dividends_total,
       count(*) FILTER (WHERE stock_splits > 0)  AS split_events
FROM core.price_daily
GROUP BY ticker
ORDER BY ticker;

SELECT ticker, trade_date, stock_splits
FROM core.price_daily
WHERE stock_splits > 0
ORDER BY ticker, trade_date;

SELECT ticker, trade_date, round(adj_close / close, 6) AS adj_to_close_ratio
FROM core.price_daily
WHERE trade_date = (SELECT max(trade_date) FROM core.price_daily)
ORDER BY ticker;

SELECT ticker, trade_date
FROM core.price_daily
WHERE volume = 0
ORDER BY ticker, trade_date;
