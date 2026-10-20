# Metric Definitions

Companion to [`research_specification.md`](research_specification.md). Every metric below is computed identically in SQL, Python, Tableau and the report. The single implementation is [`scripts/metrics.py`](../scripts/metrics.py), checked by the offline tests in [`tests/test_metrics.py`](../tests/test_metrics.py).

## Global conventions
- **Instruments:** BBCA, BMRI, BBRI (banks), IHSG (market). Source table: `core.price_daily`.
- **Return day:** a trading day present for all four tickers (verified: no gaps). First return date 2021-01-04; its prior close is 2020-12-30. 1,381 return days.
- **Price basis:** primary = `close` (split-adjusted, not dividend-adjusted). Sensitivity = `adj_close` (banks only).
- **Frequency and annualization:** daily returns, 252 trading days per year. Realized trading days per year in the data are 236–247; see design decision 1.
- **Regimes** (assigned by the return's own trade date): R1 2021-01-01 to 2022-08-22; R2 2022-08-23 to 2024-09-17; R3 2024-09-18 to 2026-05-19; Stub 2026-05-20 to 2026-09-30 (descriptive only).
- **Alignment:** every comparison uses the same set of return days for the bank and the IHSG. No forward-filling of missing days.
- **Risk-free rate:** Bank Indonesia policy rate from `ref.bi_rate_decision`, via view `analytics.rf_daily`; a decision applies from the next trading day.
- **Standard deviation:** sample (n − 1).

---

## M1. Simple daily return
- **Research question:** all (input to every metric).
- **Formula:** $`r_t = P_t / P_{t-1} - 1`$
- **Variables:** $`P_t`$ = close on trade date $`t`$; $`P_{t-1}`$ = close on the previous trading day for the same ticker.
- **Reference:** methodological convention; no citation needed.
- **Assumptions / conventions:** simple (arithmetic) returns, because they aggregate across instruments and match the SQL `lag()` used in validation. Price return excludes dividends.
- **Required fields:** `ticker`, `trade_date`, `close`.
- **Implementation:** SQL view `analytics.return_daily` using `lag(close) OVER (PARTITION BY ticker ORDER BY trade_date)`; Python `pct_change()` on the same data.
- **Validation:** Python vs SQL equality to 1e-12 on all 5,524 return rows; hand-calculate three days (including BBCA's 2021-10-13 split day and BMRI's 2026-05-11 ex-dividend day).
- **Interpretation:** the one-day percentage change in price.
- **Limitations:** a dividend drop is read as a loss (BMRI 2026-05-11: −8.21% price, −0.07% adjusted).

## M2. Cumulative return
- **Question:** SRQ1 (how much did each instrument grow over a period).
- **Formula:** $`\mathrm{CR} = \prod_t (1 + r_t) - 1`$ over the period's return days.
- **Variables:** $`r_t`$ from M1.
- **Reference:** convention.
- **Assumptions:** returns compound; no cash flows other than the dividends embedded in the sensitivity series.
- **Fields:** M1 output.
- **Implementation:** SQL `exp(sum(ln(1 + r)))`; Python `(1 + r).prod()`.
- **Validation:** equals last close / first prior close − 1 (on the split-adjusted close); matches a hand calculation over one regime.
- **Interpretation:** total price change over the period.
- **Limitations:** path-independent, so it hides volatility and drawdown; excludes dividends in the primary series.

## M3. Annualized return
- **Question:** SRQ1.
- **Formula:** $`\mathrm{AR} = (1 + \mathrm{CR})^{365.25/D} - 1`$, with $`D`$ the number of calendar days from the prior close of the first return day to the last date. Alternative reported in the sensitivity: $`(1 + \mathrm{CR})^{252/n} - 1`$, with $`n`$ the number of return days.
- **Reference:** convention.
- **Assumptions:** constant compound growth over the window.
- **Fields:** M2 output and the dates.
- **Implementation:** SQL and Python, same formula.
- **Validation:** compare both versions; a one-year window must give $`\mathrm{AR} \approx \mathrm{CR}`$.
- **Interpretation:** the constant yearly rate that would produce the same cumulative return.
- **Limitations:** hides path; short regimes give unstable annualized figures (do not annualize the Stub).

## M4. Annualized volatility
- **Question:** SRQ1, SRQ3.
- **Formula:** $`\sigma_{\text{ann}} = \sqrt{252}\, s_r`$, with $`s_r`$ the sample standard deviation of $`r_t`$
- **Reference:** convention; scaling by $`\sqrt{252}`$ assumes uncorrelated returns (see Lo, 2002 for the serial-correlation caveat).
- **Assumptions:** returns roughly serially uncorrelated and identically distributed.
- **Fields:** M1 output.
- **Implementation:** SQL `stddev_samp`; Python `std(ddof=1)`.
- **Validation:** Python vs SQL to 1e-10; rolling window sizes checked.
- **Interpretation:** typical yearly size of return fluctuation.
- **Limitations:** treats upside and downside equally; sensitive to a few large days (ten days above 8% are logged, not removed).

## M5. Daily risk-free rate and excess return
- **Question:** input to M6, M7, M8.
- **Formula:** $`r^f_t = \text{BIrate}_t / (100 \times 252)`$; $`e_t = r_t - r^f_t`$
- **Variables:** $`\text{BIrate}_t`$ = policy rate in force on trade date $`t`$ (decisions apply from the next trading day).
- **Reference:** convention (design decision 1).
- **Assumptions:** the policy rate proxies the short-term risk-free rate; 252 is the daily divisor even though the realized year is shorter.
- **Fields:** `analytics.rf_daily` (`trade_date`, `rate_pct`, `rf_daily`).
- **Implementation:** the view `analytics.rf_daily`; Python reads it from the database and merges on `trade_date`.
- **Validation:** view check on 2022-08-19 to 2022-08-26 (3.50 up to 2022-08-23, 3.75 from 2022-08-24); zero missing rates.
- **Interpretation:** the return needed just to match holding cash at the policy rate.
- **Limitations:** a policy rate is not a tradable return; many change dates are `secondary_unverified`, which could shift the series by days.

## M6. Sharpe ratio (full period, rolling 252-day, per regime) and confidence interval
- **Question:** main RQ and SRQ2.
- **Formula:** $`\mathrm{SR} = \bar{e} / s_e`$, the mean over the standard deviation of $`e_t`$; annualized $`\mathrm{SR}_{\text{ann}} = \sqrt{252}\, \mathrm{SR}`$.
- **Variables:** $`e_t`$ from M5.
- **Reference:** Sharpe (1966); sampling error in Lo (2002).
- **Assumptions:** the $`\sqrt{252}`$ scaling is exact only if daily excess returns are serially uncorrelated (Lo, 2002); the regime Sharpe uses only the return days inside that regime.
- **Fields:** `close`, `trade_date`, `rate_pct`.
- **Implementation:** Python (rolling window of exactly 252 return days; first value on the 252nd return day). Block bootstrap interval for each instrument and regime (stationary resampling of paired days so the dates stay aligned; resamples and block length as in design decision 3); also the Lo (2002) asymptotic standard error, for comparison.
- **Validation:** SQL recomputation for the full period and for each regime; a hand calculation on a 20-day sample; check window sizes and first-valid dates.
- **Interpretation:** excess return earned per unit of total volatility over the period. Intervals are reported descriptively. Added 2026-10-19 (H3; see the amendment log in the specification): the difference between each bank's Sharpe ratio and the IHSG's is tested with the Ledoit and Wolf (2008) studentized circular block bootstrap on the paired daily excess returns (notebook `07_sharpe_difference`); differences between banks and between regimes are not tested.
- **Limitations:** in-sample; sensitive to window and risk-free choice; the Stub has too few days for a reliable interval (descriptive only); price returns understate bank total return.

## M7. CAPM beta, alpha and R² (full period and per regime) — H1 and H2
- **Question:** main RQ (variance explained by IHSG exposure), SRQ3.
- **Formula:** $`e_{i,t} = \alpha_i + \beta_i\, e_{m,t} + \varepsilon_{i,t}`$, estimated by OLS; $`R^2 = 1 - \mathrm{SS}_{\text{res}} / \mathrm{SS}_{\text{tot}}`$.
- **Variables:** $`e_i`$ = bank excess return, $`e_m`$ = IHSG excess return (M5).
- **Reference:** Sharpe (1964).
- **Assumptions:** one factor; linear relation; a stable beta within each regime (checked by comparing regimes). Standard errors are heteroskedasticity-robust (HC3). Autocorrelation is diagnosed (Ljung–Box) and reported.
- **Fields:** M5 output for the bank and the IHSG on identical dates.
- **Implementation:** statsmodels OLS per bank and per regime.
- **Validation:** SQL `regr_slope`, `regr_intercept`, `regr_r2` on the same joined data; match to 1e-8; an independent manual $`\mathrm{Cov}(e_i, e_m) / \mathrm{Var}(e_m)`$ calculation.
- **Interpretation:** $`\beta`$ = sensitivity to the market; R² = proportion of the bank's return variance explained by IHSG exposure in the sample.
  - H1: t-test of $`\beta_i = 1`$.
  - H2: R² per regime with bootstrap intervals for each regime and for the pairwise differences; the Stub is excluded from H1 and H2.
- **Limitations:** in-sample and descriptive; R² is not causation; the three banks are a large part of the IHSG itself, so exposure is partly mechanical (the market is not independent of the stock).

## M8. Dimson beta (sensitivity)
- **Question:** SRQ3 robustness (is beta biased by non-synchronous trading?).
- **Formula:** $`e_{i,t} = \alpha + \sum_{k=-1}^{1} \beta_k\, e_{m,t+k} + \varepsilon_t`$; Dimson beta $`= \sum_k \beta_k`$.
- **Reference:** Dimson (1979).
- **Assumptions:** one lead and one lag capture the delay; the sum of slopes estimates beta.
- **Fields:** as M7, plus the lagged and led IHSG excess return (first and last return days lose one observation).
- **Implementation:** statsmodels OLS with shifted regressors.
- **Validation:** with k = 0 only, it must reproduce M7 exactly.
- **Interpretation:** if the Dimson beta is close to the M7 beta, thin trading is not an issue for these liquid stocks.
- **Limitations:** the three banks are highly liquid, so a large difference is not expected; extra regressors reduce precision; reported only as a sensitivity.

## M9. Maximum drawdown
- **Question:** SRQ1.
- **Formula:** $`\mathrm{MDD} = \min_t \left( P_t / \max_{s \le t} P_s - 1 \right)`$, reported with the peak date, trough date and recovery date (or "not recovered").
- **Reference:** convention.
- **Assumptions:** computed on split-adjusted close, so dividend drops are counted as losses; computed over the full period and within each regime (running maximum resets at the start of each regime).
- **Fields:** `close`, `trade_date`.
- **Implementation:** SQL window `max() OVER (ORDER BY trade_date ROWS UNBOUNDED PRECEDING)`; Python `cummax`.
- **Validation:** verify on a small hand-made price series; compare SQL and Python.
- **Interpretation:** the worst peak-to-trough loss an investor would have experienced.
- **Limitations:** a single worst episode; depends on the start date; price-based.

## M10. Total-return sensitivity (banks only)
- **Question:** SRQ4.
- **Formula:** repeat M1–M9 with P = `adj_close`.
- **Reference:** convention; Adj Close is not assumed to be a complete total-return series in every case.
- **Assumptions:** the yfinance dividend adjustment is correct; it was checked arithmetically during data verification (`scripts/verify_yfinance.py`; expected factor = 1 − dividend / previous close).
- **Fields:** `adj_close`.
- **Implementation:** same code with a price-column switch.
- **Validation:** adjustment ratio is 1.000000 on the last date (confirmed); differences versus the primary series are reported next to it.
- **Interpretation:** how much of the conclusions depend on ignoring dividends.
- **Limitations:** the IHSG has no dividends here, so the like-for-like comparison with the index is only valid on the price basis; this series is therefore labelled as a sensitivity.

---

## Design decisions
1. **Annualization.** 252 for volatility, Sharpe and the daily risk-free divisor; calendar-time compounding for annualized return. The data has 236–247 trading days a year (about 241), so the 252 scaling is an approximation of about 2% ($`\sqrt{241/252} \approx 0.978`$). This is stated in the limitations of M4, M5 and M6.
2. **Standard errors.** HC3 robust errors for the CAPM regression, with the Ljung–Box result reported.
3. **Bootstrap settings.** 10,000 resamples, block size 10 days (sensitivity at 5 and 21), fixed random seed. Reference: Ledoit and Wolf (2008).
4. **H2 method.** Bootstrap intervals for the R² difference between regimes (R1 vs R2, R2 vs R3, R1 vs R3). The differing regime lengths are stated with the results.
5. **Peer criterion 5.** Relaxed to a visual spot-check of 5 random dates against the Yahoo Finance or IDX website. The Stooq block is documented in the data-quality report.
6. **Peer market-cap date.** 2021-01-04, recorded before screening.
