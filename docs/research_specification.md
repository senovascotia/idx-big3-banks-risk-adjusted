# Research Specification

Status: implemented. This is the design document written before any data were analysed: the regime dates, hypotheses and peer criteria below were fixed in advance. Changes made after the design stage are listed in the amendment log. The metric formulas are in [`metric_definitions.md`](metric_definitions.md), and the results are in the [analytical report](../report/report_draft.md).

**Amendment log.**
- 2026-10-19 (after a methodological review of the first draft of the report): hypothesis H3 added. The main research question compares each bank's Sharpe ratio with the IHSG's, and overlapping confidence intervals do not test that comparison. The difference is now tested directly with the Ledoit and Wolf (2008) paired bootstrap test (sections 7, 11, 12; notebook `07_sharpe_difference`). The reference list was checked against Crossref and the Dimson (1979) DOI corrected.

## 1. Project title
Risk-Adjusted Performance and Market Exposure of Indonesia's Three Largest Banks (BBCA, BMRI, BBRI) versus the IHSG, 2021–2026

## 2. Background and motivation
BBCA, BMRI and BBRI are among the largest and most heavily traded constituents of the Indonesian market, so their behaviour matters to anyone benchmarking against the IHSG. A raw return ranking ignores risk, so the project compares risk-adjusted returns and measures how much of each bank's return variation is tied to the overall market.

## 3. Business problem
An investor or analyst holding or considering large Indonesian bank stocks needs to know whether they have compensated holders for the risk taken relative to simply holding the market, and how much of their movement is market-driven.

## 4. Analytical problem
Using daily price data, estimate and compare (a) risk-adjusted performance and (b) exposure to the IHSG for each bank over a fixed historical window, including how both change over time and across pre-defined regimes.

## 5. Main research question
From January 2021 through September 2026, did BBCA, BMRI and BBRI deliver better risk-adjusted returns than the IHSG and a justified set of regional bank peers, and what proportion of each bank's return variance is explained by its exposure to the IHSG under a single-factor CAPM specification?

## 6. Supporting research questions
1. How do cumulative and annualized returns, volatility and maximum drawdown compare across the three banks and the IHSG?
2. How does the Sharpe ratio vary over time (rolling 252 trading days) and across regimes?
3. What are each bank's CAPM beta and R² against the IHSG, and are they stable across regimes?
4. Do the conclusions change when dividends are included (total-return sensitivity)?
5. (Optional extension, only if 1–4 are complete) How do the banks compare with the bounded peer set?

## 7. Hypotheses
Descriptive expectations (reported, not tested): the banks have betas near but not necessarily equal to 1; the IHSG has lower volatility than any single bank; stress periods produce the deepest drawdowns.
Testable (only these are tested, with the test and assumptions stated before running):
- H1: beta for each bank differs from 1 (t-test on the OLS slope, with heteroskedasticity-robust standard errors).
- H2: R² differs across regimes R1, R2 and R3 (bootstrap intervals for each regime and for the pairwise differences; descriptive if assumptions fail).
- H3 (added 2026-10-19, see the amendment log): the Sharpe ratio of each bank differs from that of the IHSG. Tested with the Ledoit and Wolf (2008) studentized circular block bootstrap on the paired daily excess returns (10,000 resamples, block size 10 days with 5 and 21 as sensitivity, fixed seed). Primary family: the full period, three tests, Holm-adjusted. Secondary: R1, R2 and R3, Holm-adjusted across all twelve tests. Two simplifications against the paper are stated with the results: a Bartlett (Newey–West) kernel instead of the prewhitened quadratic-spectral kernel, and a fixed block size instead of the paper's block-size calibration.
Sharpe ratios are not tested for differences between banks or between regimes. Each Sharpe ratio's uncertainty is still reported descriptively as a confidence interval, using a stationary block bootstrap (10,000 resamples, 10-day mean block size) and the Lo (2002) asymptotic standard error for comparison. CAPM standard errors are HC3 heteroskedasticity-robust.
No causal claims are made. Results are in-sample and descriptive.

## 8. Scope and time period
- First return date 2021-01-04; last data date 2026-09-30 (verified populated). 1,381 daily return observations per instrument; the 3 trading days in late Dec 2020 serve only as the prior close.
- Regimes are defined ex ante by policy-rate phase, not fitted to the data. A return belongs to the regime containing its own trade date.

| Regime | Label | Dates |
|---|---|---|
| R1 | Low-rate | 1 Jan 2021 – 22 Aug 2022 |
| R2 | Tightening and high plateau | 23 Aug 2022 – 17 Sep 2024 |
| R3 | Easing | 18 Sep 2024 – 19 May 2026 |
| Stub | Re-tightening | 20 May 2026 – 30 Sep 2026 (descriptive only, no tests) |

## 9. Instruments and benchmark
| Role | Ticker | Source symbol |
|---|---|---|
| Primary | BBCA, BMRI, BBRI | BBCA.JK, BMRI.JK, BBRI.JK |
| Benchmark | IHSG (JCI) | ^JKSE |

Peers (optional, bounded): a bank is included only if it meets all five criteria. If fewer than two peers qualify with clean data, the peer comparison is dropped.
1. Listed commercial or universal bank on an ASEAN-6 exchange main board.
2. Market cap within 0.25x to 4x of the median market cap of BBCA, BMRI and BBRI at one fixed date (date to be fixed and recorded before screening).
3. Retail and commercial banking as the main business, with loans and deposits as the dominant revenue source. Pure investment banks and digital-only banks are excluded.
4. Traded on at least 95% of local trading days in the sample period.
5. At least 99% of daily observations present in yfinance, and a visual spot-check of 5 random dates against the Yahoo Finance or IDX website shows no obvious gaps. (Relaxed from an automated independent check because Stooq blocks programmatic access and Investing.com scraping is not permitted; the block is documented in the data-quality report.)

The fixed date for criterion 2 is 2021-01-04, recorded before screening.

## 10. Data sources and rationale
- Prices: yfinance (Yahoo Finance), auto_adjust=False, so Close (split-adjusted) and Adj Close (split- and dividend-adjusted) are stored separately. Chosen for free access, daily history from 2020, and corporate-action fields. Limitations: unofficial, can be revised, no independent cross-check was possible (Stooq blocks programmatic access; scraping Investing.com is not permitted).
- Risk-free rate: Bank Indonesia policy rate (BI7DRR, renamed BI-Rate from 2023-12-21), from the Kontan decision table, cross-checked to BI SEKI period-end levels. Each row carries a verification status (bi_official, multiple_news, secondary_unverified); the change dates for many rows remain unchecked against bi.go.id.
- Retrieval details are stored in raw.load_log.

## 11. Theoretical foundations and references
- CAPM and single-factor market exposure: Sharpe (1964).
- Reward-to-variability ratio (Sharpe ratio): Sharpe (1966).
- Sampling uncertainty of the Sharpe ratio and its annualization under serial correlation: Lo (2002).
- Beta estimation when prices trade infrequently or non-synchronously (lead and lag terms on the market return): Dimson (1979).
- Testing the difference between two Sharpe ratios on paired time-series returns (H3): Ledoit and Wolf (2008).
- Methods used for inference and diagnostics: the stationary bootstrap (Politis & Romano, 1994), HC3 standard errors (MacKinnon & White, 1985), Newey–West standard errors and lag rule (Newey & West, 1987, 1994), the Ljung–Box test (Ljung & Box, 1978) and the Holm adjustment for multiple tests (Holm, 1979).
- Fama and French (1993) is not planned (no factor extension).

Verification status of the reference list is given under References.

## 12. Metrics and definitions (all daily, 252 trading days per year)
| Metric | Definition |
|---|---|
| Simple return | $`r_t = P_t / P_{t-1} - 1`$, $`P`$ = split-adjusted Close (primary); Adj Close for the total-return sensitivity (banks only) |
| Cumulative return | $`\prod_t (1 + r_t) - 1`$ |
| Annualized return | $`(1 + \mathrm{CR})^{252/n} - 1`$, $`n`$ = number of return days (implemented with calendar-time compounding; see section 18) |
| Annualized volatility | $`\sqrt{252}\, s_r`$, with $`s_r`$ the sample standard deviation of $`r_t`$ |
| Daily risk-free | $`r^f_t = \text{rate}_t / (100 \times 252)`$, rate applying from the next trading day after the decision |
| Excess return | $`e_t = r_t - r^f_t`$ |
| Sharpe ratio | $`\sqrt{252}\,\bar{e} / s_e`$; full period, rolling 252-day, and per regime |
| CAPM beta, R² | OLS of the bank excess return on the IHSG excess return: $`e_{i,t} = \alpha + \beta\, e_{m,t} + \varepsilon_t`$; R² = proportion of return variance explained by IHSG exposure (in-sample, descriptive) |
| Sharpe confidence interval | Block-bootstrap interval (primary) and Lo (2002) asymptotic standard error (comparison); descriptive only |
| Sharpe difference against the IHSG (H3) | $`\Delta = \mathrm{SR}_b - \mathrm{SR}_m`$ on paired daily excess returns; Ledoit and Wolf (2008) studentized circular block bootstrap interval and p-value |
| Dimson beta (sensitivity) | Sum of the slopes on the contemporaneous, lagged and led IHSG excess return; checks whether beta is understated by non-synchronous trading |
| Maximum drawdown | $`\min_t \left( P_t / \max_{s \le t} P_s - 1 \right)`$ |

Metric definitions must be identical in SQL, Python, Tableau and the report. A formal metric-definition table (assumptions, validation, limitations per metric) is the first deliverable of the next task.

## 13. Proposed analysis methods
SQL views (analytics schema) for returns and risk-free alignment. The Python analysis (pandas, NumPy, statsmodels) is done in Jupyter notebooks in VS Code, which hold the narrative, results and charts. Metric formulas live in a small module of plain functions (`scripts/metrics.py`) that the notebooks import, so each definition exists once. Database loading stays in scripts (`load_prices.py`, `db_access.py`). Every notebook must run top to bottom with Restart and Run All, use a fixed random seed for the bootstrap, and keep credentials out of cells and outputs. Python is validated independently against SQL and hand-computed samples.

## 14. Proposed visualizations
Cumulative return vs IHSG; rolling 252-day Sharpe; drawdown chart; beta and R² by bank and regime; one summary table. The Tableau dashboard should convey the main finding in about 60 seconds and label period, return convention, benchmark, annualization, source and limitations.

## 15. Data-quality requirements and status
Met so far (queries A–G): equal row counts per ticker and year, no date gaps across tickers, no open outside the day's range, 10 large-move days all logged, split and dividend counts as expected, Adj/Close ratio 1.0 on the last date, IHSG volume = 0 on 2 days (not used). Outstanding: no independent price source; many BI change dates unverified; BMRI 2026-05-11 shows an −8.21% price return that is mostly a dividend.

## 16. Success criteria
- At least three pieces of quantitative evidence (e.g. Sharpe by regime, beta/R², drawdown comparison).
- Python results match SQL to a stated tolerance on sampled metrics.
- Every claim traces to a calculation, data source or labelled interpretation.
- Analysis reruns in roughly 30 minutes after setup.

## 17. Expected deliverables
Data dictionary and data-quality report; metric-definition table; SQL scripts; Python scripts/notebook; Tableau dashboard (or screenshots); final report with reference audit; README and reproducibility instructions on GitHub (no credentials or restricted data).

## 18. Limitations and risks
- In-sample, historical, descriptive; not forward-looking investment advice.
- Selection: the three largest banks were chosen, which can overstate how representative they are.
- Price returns exclude dividends; yfinance Adj Close may not be a full total-return series.
- The regression assumes a single factor; residual autocorrelation and heteroskedasticity are handled with robust errors and reported.
- Sharpe ratios are sensitive to the risk-free convention and window; regimes with few observations (2026 stub) are descriptive only.
- Currency: peers outside Indonesia need their own local risk-free rates; otherwise only local-currency price metrics are compared.
- Unverified BI rate dates may shift the risk-free series by days.
- Annualization uses 252 trading days, but the data has 236–247 per year (about 241 on average). Scaling volatility, Sharpe and the daily risk-free divisor by 252 is an approximation of about 2% ($`\sqrt{241/252} \approx 0.978`$). Annualized return uses calendar-time compounding instead.

## 19. Prioritized task plan
1. Metric-definition table. **Next.**
2. SQL returns and risk-free views; validate against the data already loaded.
3. Notebook `01_validate_returns` (Python-versus-SQL validation of M1, M2, M5). Notebook `02_performance_risk` (returns, volatility, drawdown, Sharpe: full, rolling, regime).
4. Notebook `03_capm` (CAPM regressions, Dimson beta, H1, H2 and diagnostics).
5. Hand checks for the metric functions and Sharpe and drawdown samples.
6. Total-return sensitivity.
7. Tableau dashboard and validation against Python.
8. Optional peer extension (only if 1–7 are done).
9. Report, reference audit, README, publication.

## References
- Dimson, E. (1979). Risk measurement when shares are subject to infrequent trading. *Journal of Financial Economics, 7*(2), 197–226. https://doi.org/10.1016/0304-405X(79)90013-8
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics, 6*(2), 65–70. https://www.jstor.org/stable/4615733
- Ledoit, O., & Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. *Journal of Empirical Finance, 15*(5), 850–859. https://doi.org/10.1016/j.jempfin.2008.03.002
- Ljung, G. M., & Box, G. E. P. (1978). On a measure of lack of fit in time series models. *Biometrika, 65*(2), 297–303. https://doi.org/10.1093/biomet/65.2.297
- Lo, A. W. (2002). The statistics of Sharpe ratios. *Financial Analysts Journal, 58*(4), 36–52. https://doi.org/10.2469/faj.v58.n4.2453
- MacKinnon, J. G., & White, H. (1985). Some heteroskedasticity-consistent covariance matrix estimators with improved finite sample properties. *Journal of Econometrics, 29*(3), 305–325. https://doi.org/10.1016/0304-4076(85)90158-7
- Newey, W. K., & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica, 55*(3), 703–708. https://doi.org/10.2307/1913610
- Newey, W. K., & West, K. D. (1994). Automatic lag selection in covariance matrix estimation. *The Review of Economic Studies, 61*(4), 631–653. https://doi.org/10.2307/2297912
- Politis, D. N., & Romano, J. P. (1994). The stationary bootstrap. *Journal of the American Statistical Association, 89*(428), 1303–1313. https://doi.org/10.1080/01621459.1994.10476870
- Sharpe, W. F. (1964). Capital asset prices: A theory of market equilibrium under conditions of risk. *The Journal of Finance, 19*(3), 425–442. https://doi.org/10.1111/j.1540-6261.1964.tb02865.x
- Sharpe, W. F. (1966). Mutual fund performance. *The Journal of Business, 39*(S1), 119–138. https://doi.org/10.1086/294846

Verification (2026-10-19): every DOI above was resolved against the Crossref metadata service and the authors, year, title, journal, volume, issue and pages match, with three qualifications. (1) The Dimson DOI previously listed here, 10.1016/0304-405X(79)90012-6, belongs to a different article (Litzenberger and Ramaswamy, 1979, pp. 163–195) and has been replaced. (2) Crossref gives only the first page for Sharpe (1966) and Newey and West (1987); the last pages (138 and 708) were confirmed from secondary listings (Sharpe's Stanford publication list and a MathWorks reference; Wikipedia and the Econometric Society listing). Crossref gives the Sharpe (1966) issue as S1 (Vol. 39, No. 1, Part 2). (3) Holm (1979) has no DOI; its details and JSTOR stable URL were confirmed from secondary sources (citation listings and Wikipedia), not from the JSTOR page itself. The Ledoit and Wolf (2008) method description was checked against the published article (section 3.2.2 and Remark 3.2).
The stationary block bootstrap used for the single Sharpe ratio intervals is from Politis and Romano (1994), not from Lo (2002). Ledoit and Wolf (2008) is the method used for H3.
