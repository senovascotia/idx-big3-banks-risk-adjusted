CREATE OR REPLACE VIEW analytics.return_daily AS
WITH r AS (
    SELECT ticker, trade_date, close, adj_close,
           (close     / lag(close)     OVER w - 1)::double precision AS ret_close,
           (adj_close / lag(adj_close) OVER w - 1)::double precision AS ret_adj
    FROM core.price_daily
    WINDOW w AS (PARTITION BY ticker ORDER BY trade_date)
)
SELECT ticker, trade_date, close, adj_close, ret_close, ret_adj
FROM r
WHERE trade_date >= DATE '2021-01-04';

CREATE OR REPLACE VIEW analytics.excess_return_daily AS
SELECT r.ticker,
       r.trade_date,
       CASE
           WHEN r.trade_date <= DATE '2022-08-22' THEN 'R1'
           WHEN r.trade_date <= DATE '2024-09-17' THEN 'R2'
           WHEN r.trade_date <= DATE '2026-05-19' THEN 'R3'
           ELSE 'Stub'
       END AS regime,
       r.ret_close,
       r.ret_adj,
       f.rate_pct,
       f.rf_daily::double precision AS rf_daily,
       r.ret_close - f.rf_daily::double precision AS excess_close,
       r.ret_adj   - f.rf_daily::double precision AS excess_adj
FROM analytics.return_daily AS r
JOIN analytics.rf_daily AS f USING (trade_date);

SELECT ticker, count(*) AS n_returns, min(trade_date) AS first_date, max(trade_date) AS last_date
FROM analytics.return_daily
GROUP BY ticker
ORDER BY ticker;

SELECT count(*) FILTER (WHERE ret_close IS NULL) AS null_ret_close,
       count(*) FILTER (WHERE ret_adj IS NULL)   AS null_ret_adj
FROM analytics.return_daily;

SELECT ticker, regime, count(*) AS n_days, min(trade_date) AS first_date, max(trade_date) AS last_date
FROM analytics.excess_return_daily
GROUP BY ticker, regime
ORDER BY ticker, regime;

SELECT count(*) AS rows_in_excess_view,
       count(*) FILTER (WHERE rf_daily IS NULL OR excess_close IS NULL) AS null_excess
FROM analytics.excess_return_daily;

SELECT ticker, trade_date, round((ret_close * 100)::numeric, 2) AS ret_close_pct,
       round((ret_adj * 100)::numeric, 2) AS ret_adj_pct
FROM analytics.return_daily
WHERE (ticker = 'BBCA' AND trade_date = DATE '2021-10-13')
   OR (ticker = 'BMRI' AND trade_date = DATE '2026-05-11')
ORDER BY ticker, trade_date;

WITH cum AS (
    SELECT ticker, exp(sum(ln(1 + ret_close))) - 1 AS cum_from_returns
    FROM analytics.return_daily
    GROUP BY ticker
),
ends AS (
    SELECT p.ticker,
           p.close / (SELECT q.close FROM core.price_daily q
                      WHERE q.ticker = p.ticker AND q.trade_date = DATE '2020-12-30') - 1 AS cum_from_prices
    FROM core.price_daily p
    WHERE p.trade_date = (SELECT max(trade_date) FROM core.price_daily)
)
SELECT c.ticker,
       round(c.cum_from_returns::numeric, 6) AS cum_from_returns,
       round(e.cum_from_prices::numeric, 6)  AS cum_from_prices,
       abs(c.cum_from_returns - e.cum_from_prices::double precision) < 1e-9 AS match
FROM cum c
JOIN ends e USING (ticker)
ORDER BY c.ticker;
