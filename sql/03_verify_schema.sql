SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('raw', 'ref', 'core', 'analytics')
ORDER BY table_schema, table_name;

SELECT * FROM ref.instrument ORDER BY ticker;

SELECT conname, contype, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'core.price_daily'::regclass
ORDER BY contype, conname;

BEGIN;
INSERT INTO core.price_daily (ticker, trade_date, open, high, low, close, adj_close, volume, source_load_id)
VALUES ('BBCA', '2021-01-04', 100, 90, 95, 95, 95, 1, 1);
ROLLBACK;

SELECT count(*) FROM core.price_daily;
