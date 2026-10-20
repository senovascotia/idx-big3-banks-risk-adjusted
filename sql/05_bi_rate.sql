INSERT INTO ref.bi_rate_decision (decision_date, rate_pct, policy_rate_name, verification_status, source_note) VALUES
    ('2020-11-19', 3.75, 'BI7DRR', 'secondary_unverified', 'Opening level. 3.75% confirmed by SEKI year-end 2020; decision date not checked.'),
    ('2021-02-18', 3.50, 'BI7DRR', 'secondary_unverified', 'Kontan table'),
    ('2022-08-23', 3.75, 'BI7DRR', 'bi_official',          'bi.go.id release: meeting 22-23 Aug 2022, +25 bp'),
    ('2022-09-22', 4.25, 'BI7DRR', 'secondary_unverified', 'Kontan table'),
    ('2022-10-20', 4.75, 'BI7DRR', 'secondary_unverified', 'Kontan table'),
    ('2022-11-17', 5.25, 'BI7DRR', 'secondary_unverified', 'Kontan table'),
    ('2022-12-22', 5.50, 'BI7DRR', 'secondary_unverified', 'Kontan table; 5.50% is the SEKI year-end 2022 level'),
    ('2023-01-19', 5.75, 'BI7DRR', 'secondary_unverified', 'Kontan table'),
    ('2023-10-19', 6.00, 'BI7DRR', 'secondary_unverified', 'Kontan table; 6.00% is the SEKI year-end 2023 level'),
    ('2024-04-24', 6.25, 'BI-Rate', 'secondary_unverified', 'Kontan table; policy rate renamed BI-Rate from 2023-12-21'),
    ('2024-09-18', 6.00, 'BI-Rate', 'multiple_news',       'Several news outlets; first cut after the April 2024 hike. bi.go.id release not retrieved.'),
    ('2025-01-15', 5.75, 'BI-Rate', 'secondary_unverified', 'Kontan table'),
    ('2025-05-21', 5.50, 'BI-Rate', 'secondary_unverified', 'Kontan table'),
    ('2025-07-16', 5.25, 'BI-Rate', 'secondary_unverified', 'Kontan table'),
    ('2025-08-20', 5.00, 'BI-Rate', 'secondary_unverified', 'Kontan table; 5.00% is the SEKI August 2025 level'),
    ('2025-09-17', 4.75, 'BI-Rate', 'secondary_unverified', 'Kontan table; 4.75% is the SEKI September 2025 level'),
    ('2026-05-20', 5.25, 'BI-Rate', 'bi_official',          'bi.go.id BI-Rate page'),
    ('2026-06-09', 5.50, 'BI-Rate', 'bi_official',          'bi.go.id BI-Rate page'),
    ('2026-06-18', 5.75, 'BI-Rate', 'bi_official',          'bi.go.id BI-Rate page');

WITH expected(label, as_of, seki_rate) AS (
    VALUES ('end 2020',  DATE '2020-12-31', 3.75),
           ('end 2021',  DATE '2021-12-31', 3.50),
           ('end 2022',  DATE '2022-12-31', 5.50),
           ('end 2023',  DATE '2023-12-31', 6.00),
           ('end 2024',  DATE '2024-12-31', 6.00),
           ('Aug 2025',  DATE '2025-08-31', 5.00),
           ('Sep 2025',  DATE '2025-09-30', 4.75),
           ('Apr 2026',  DATE '2026-04-30', 4.75),
           ('May 2026',  DATE '2026-05-31', 5.25),
           ('Jun 2026',  DATE '2026-06-30', 5.75),
           ('Sep 2026',  DATE '2026-09-30', 5.75)
)
SELECT e.label, e.seki_rate,
       (SELECT d.rate_pct FROM ref.bi_rate_decision d
         WHERE d.decision_date <= e.as_of ORDER BY d.decision_date DESC LIMIT 1) AS table_rate,
       CASE WHEN e.seki_rate = (SELECT d.rate_pct FROM ref.bi_rate_decision d
                                 WHERE d.decision_date <= e.as_of ORDER BY d.decision_date DESC LIMIT 1)
            THEN 'ok' ELSE 'MISMATCH' END AS check_result
FROM expected e
ORDER BY e.as_of;

CREATE VIEW analytics.rf_daily AS
SELECT t.trade_date,
       r.rate_pct,
       r.rate_pct / 100 / 252 AS rf_daily
FROM (SELECT DISTINCT trade_date FROM core.price_daily) AS t
LEFT JOIN LATERAL (
    SELECT b.rate_pct
    FROM ref.bi_rate_decision AS b
    WHERE b.decision_date < t.trade_date
    ORDER BY b.decision_date DESC
    LIMIT 1
) AS r ON true;

SELECT trade_date, rate_pct, round(rf_daily, 8) AS rf_daily
FROM analytics.rf_daily
WHERE trade_date BETWEEN '2022-08-19' AND '2022-08-26'
ORDER BY trade_date;

SELECT count(*) AS dates_without_rate FROM analytics.rf_daily WHERE rate_pct IS NULL;
