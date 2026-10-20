# Replication Guide

How to rebuild the database, rerun every calculation and reopen the dashboard. A full run takes about 30 minutes after setup, mostly the bootstrap steps. Seeds are fixed, so the numbers reproduce exactly from the same data.

## 1. Prerequisites

- **PostgreSQL**, a recent version, with any client (the project was run with DataGrip)
- **Python 3.13** (the version used; [`requirements.txt`](../requirements.txt) pins the exact package versions that produced the results)
- **Tableau Desktop** (Free Edition works) for the dashboard

## 2. Environment setup

```bash
git clone https://github.com/senovascotia/idx-big3-banks-risk-adjusted.git
cd idx-big3-banks-risk-adjusted
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

**Database credentials are never stored in the repository.** The scripts and notebooks read the standard PostgreSQL environment variables (listed in [`.env.example`](../.env.example)). Any that are missing are requested at run time, with the password entered through a hidden prompt.

| Variable | Default |
|---|---|
| `PGHOST` | `localhost` |
| `PGPORT` | `5432` |
| `PGDATABASE` | `idx_bank_risk` |
| `PGUSER` | asked at run time |
| `PGPASSWORD` | asked at run time (hidden input) |

The code does not load a `.env` file. If you keep one locally (it is gitignored), export its variables into your shell before running.

## 3. Step 1: SQL (build and load the database)

| Order | File | Connected to |
|---|---|---|
| 1 | `sql/01_create_database.sql` (auto-commit) | `postgres` |
| 2 | `sql/02_schema.sql` | `idx_bank_risk` |
| 3 | `sql/03_verify_schema.sql` | `idx_bank_risk` |
| 4 | `python -I scripts/load_prices.py` (loads prices once and refuses to reload) | — |
| 5 | `sql/04_validate_prices.sql` | `idx_bank_risk` |
| 6 | `sql/05_bi_rate.sql` | `idx_bank_risk` |
| 7 | `sql/06_cleaning_log.sql` (run once only) | `idx_bank_risk` |
| 8 | `sql/07_return_views.sql` | `idx_bank_risk` |

## 4. Step 2: Python (analysis)

Run the offline tests, then each notebook with *Restart and Run All* on the project's `.venv` kernel:

```bash
python -I tests/test_metrics.py        # 30 hand-worked tests, no database needed
```

| Notebook | Content | Checks |
|---|---|---|
| `01_validate_returns` | Python against SQL: returns, cumulative return, risk-free rate | 12 |
| `02_performance_risk` | Returns, volatility, drawdown, Sharpe (full, rolling, regime, bootstrap) | 11 |
| `03_capm` | CAPM, H1, H2, Newey–West, Holm, Dimson, shock-day sensitivity | 18 |
| `04_hand_checks` | Hand and SQL checks of every metric on the real data | 50 |
| `05_total_return_sensitivity` | Banks on the dividend-adjusted basis | 16 |
| `06_figures` | Figures 1–7 | 8 |
| `07_sharpe_difference` | H3 Ledoit–Wolf test, Figure 8, market-implied returns | 8 |
| `08_tableau_extracts` | CSV extracts for Tableau (written to `tableau/data/`, gitignored) | 13 |

Every notebook ends with an assertion that all of its checks passed. Tables go to `reports/` (gitignored), and figures to `reports/figures/`.

**Validation tolerances.** SQL against Python: daily returns 1e-12; volatility and drawdown 1e-10; cumulative return and Sharpe ratio 1e-9; CAPM coefficients 1e-8.

## 5. Step 3: Tableau (dashboard)

1. Run notebook `08_tableau_extracts` to create the seven CSVs in `tableau/data/`.
2. Open `tableau/bank_dashboard_final.twb`. If your project folder differs, re-point the data sources (*Data → Edit Data Source*) to your `tableau/data/` folder.
3. Optionally, regenerate a base workbook with `python tableau/build_workbook.py`. This writes `bank_dashboard.twb`; the finished, hand-polished version is `bank_dashboard_final.twb`.
4. Validate against the checklist in [`tableau/dashboard_spec.md`](../tableau/dashboard_spec.md), section 7.

## 6. Data notice

The price data come from Yahoo Finance and are **not included** in this repository; the notebooks regenerate everything from a fresh download. A fresh download may differ slightly, because Yahoo revises adjusted prices after later dividends. Check the provider's terms before redistributing any derived data.
