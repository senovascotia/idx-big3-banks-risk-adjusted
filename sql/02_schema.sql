CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE ref.instrument (
    ticker          text PRIMARY KEY,
    source_symbol   text NOT NULL UNIQUE,
    instrument_name text NOT NULL,
    instrument_type text NOT NULL CHECK (instrument_type IN ('equity', 'index')),
    role            text NOT NULL CHECK (role IN ('bank', 'benchmark', 'peer')),
    exchange        text NOT NULL,
    currency        char(3) NOT NULL
);

INSERT INTO ref.instrument VALUES
    ('BBCA', 'BBCA.JK', 'PT Bank Central Asia Tbk',              'equity', 'bank',      'Jakarta', 'IDR'),
    ('BMRI', 'BMRI.JK', 'PT Bank Mandiri (Persero) Tbk',        'equity', 'bank',      'Jakarta', 'IDR'),
    ('BBRI', 'BBRI.JK', 'PT Bank Rakyat Indonesia (Persero) Tbk','equity', 'bank',     'Jakarta', 'IDR'),
    ('IHSG', '^JKSE',   'IDX COMPOSITE',                         'index',  'benchmark', 'Jakarta', 'IDR');

CREATE TABLE ref.bi_rate_decision (
    decision_date       date PRIMARY KEY,
    rate_pct            numeric(5, 2) NOT NULL CHECK (rate_pct >= 0),
    policy_rate_name    text NOT NULL,
    verification_status text NOT NULL
        CHECK (verification_status IN ('bi_official', 'multiple_news', 'secondary_unverified')),
    source_note         text
);

CREATE TABLE raw.load_log (
    load_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source         text NOT NULL,
    source_version text,
    source_symbol  text NOT NULL,
    request_start  date NOT NULL,
    request_end    date NOT NULL,
    auto_adjust    boolean NOT NULL,
    retrieved_at   timestamptz NOT NULL DEFAULT now(),
    rows_loaded    integer NOT NULL,
    note           text
);

CREATE TABLE raw.yf_price_daily (
    load_id       bigint NOT NULL REFERENCES raw.load_log (load_id),
    source_symbol text   NOT NULL,
    trade_date    date   NOT NULL,
    open          numeric(20, 6),
    high          numeric(20, 6),
    low           numeric(20, 6),
    close         numeric(20, 6),
    adj_close     numeric(20, 6),
    volume        bigint,
    dividends     numeric(20, 8),
    stock_splits  numeric(12, 6),
    PRIMARY KEY (load_id, source_symbol, trade_date)
);

CREATE TABLE core.price_daily (
    ticker         text   NOT NULL REFERENCES ref.instrument (ticker),
    trade_date     date   NOT NULL,
    open           numeric(20, 6) NOT NULL CHECK (open > 0),
    high           numeric(20, 6) NOT NULL CHECK (high > 0),
    low            numeric(20, 6) NOT NULL CHECK (low > 0),
    close          numeric(20, 6) NOT NULL CHECK (close > 0),
    adj_close      numeric(20, 6) NOT NULL CHECK (adj_close > 0),
    volume         bigint NOT NULL CHECK (volume >= 0),
    dividends      numeric(20, 8) NOT NULL DEFAULT 0 CHECK (dividends >= 0),
    stock_splits   numeric(12, 6) NOT NULL DEFAULT 0 CHECK (stock_splits >= 0),
    source_load_id bigint NOT NULL REFERENCES raw.load_log (load_id),
    PRIMARY KEY (ticker, trade_date),
    CONSTRAINT ck_high_ge_low   CHECK (high >= low),
    CONSTRAINT ck_close_in_range CHECK (close BETWEEN low AND high)
);

CREATE INDEX ix_price_daily_trade_date ON core.price_daily (trade_date);

CREATE TABLE core.cleaning_log (
    log_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker     text REFERENCES ref.instrument (ticker),
    trade_date date,
    issue      text NOT NULL,
    decision   text NOT NULL CHECK (decision IN ('kept', 'corrected', 'excluded')),
    rationale  text NOT NULL,
    logged_at  timestamptz NOT NULL DEFAULT now()
);
