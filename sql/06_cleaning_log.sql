WITH r AS (
    SELECT ticker, trade_date, dividends,
           close     / lag(close)     OVER w - 1 AS ret_close,
           adj_close / lag(adj_close) OVER w - 1 AS ret_adj
    FROM core.price_daily
    WINDOW w AS (PARTITION BY ticker ORDER BY trade_date)
)
INSERT INTO core.cleaning_log (ticker, trade_date, issue, decision, rationale)
SELECT ticker, trade_date,
       format('Daily close return %s%% (above the 8%% investigation threshold)', round(ret_close * 100, 2)),
       'kept',
       CASE WHEN dividends > 0
            THEN format('Ex-dividend date (dividend %s IDR): the price drop is mostly the dividend; adjusted-close return is %s%%.',
                        round(dividends, 2), round(ret_adj * 100, 2))
            ELSE 'No corporate action recorded on this date. Retained as a possible genuine market move; '
                 'cause not established and not yet checked against an independent source.'
       END
FROM r
WHERE abs(ret_close) > 0.08 OR abs(ret_adj) > 0.08;

INSERT INTO core.cleaning_log (ticker, trade_date, issue, decision, rationale)
SELECT ticker, trade_date, 'Zero reported volume', 'kept',
       'Index volume is not used in any metric; prices on this date are present and valid.'
FROM core.price_daily
WHERE volume = 0;

INSERT INTO core.cleaning_log (ticker, trade_date, issue, decision, rationale) VALUES
    (NULL, NULL, 'Independent price cross-check could not be performed',
     'kept',
     'Stooq blocks programmatic access (JavaScript bot challenge); Investing.com scraping is not permitted. '
     'Prices were validated internally only: consistency across series, dividend/split adjustment arithmetic. '
     'Not compared with a second price source.'),
    (NULL, NULL, 'Close is split-adjusted; Adj Close is split- and dividend-adjusted (yfinance, auto_adjust=False)',
     'kept',
     'Primary analysis uses split-adjusted price returns (Close) for all four instruments for a like-for-like IHSG '
     'comparison. Adj Close is used only as a labelled total-return sensitivity for the three banks.');

SELECT log_id, ticker, trade_date, left(issue, 60) AS issue, decision
FROM core.cleaning_log
ORDER BY log_id;
