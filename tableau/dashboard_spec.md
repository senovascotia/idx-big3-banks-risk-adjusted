# Tableau dashboard: build guide and validation checklist

This guide describes the dashboard for the project *Risk-Adjusted Performance and Market Exposure of Indonesia's Three Largest Banks versus the IHSG, 2021–2026*, and how to check it against the validated Python results. The workbook itself is built by hand in Tableau.

## 1. What the dashboard must say in about 60 seconds

A reader should leave with three points, in this order:

1. **Risk-adjusted return against the IHSG is inconclusive.** Over the full period all three banks have slightly higher Sharpe ratios than the IHSG (differences +0.05, +0.06, +0.33), but none of the twelve tested differences is significant. The sample is too short to detect differences smaller than about 0.75.
2. **The largest divergence was in R3, the easing regime.** The banks lost about 43% in price against 19% for the IHSG; their market exposure accounts for less than half of that loss. Gaps as large occurred in the other direction in R2.
3. **Market exposure.** BBRI and BMRI moved more than one-for-one with the IHSG in R1 and R2 (beta about 1.3 to 1.45); about 40% of each bank's daily variance is shared with the index.

Everything else on the dashboard supports one of these three points. Nothing on it implies a forecast or a recommendation to buy.

## 2. Data

Run `notebooks/08_tableau_extracts.ipynb` (after notebooks 02, 03, 05 and 07). It writes these files to `tableau/data/`. Connect each one as its **own data source** (Data > New Data Source > Text file). No joins or blends are needed: every sheet uses one file.

| File | One row per | Key fields |
|---|---|---|
| `kpi.csv` | instrument | `ticker`, `price_return_pct`, `total_return_pct`, `sharpe`, `sharpe_diff_vs_ihsg`, `sharpe_diff_p`, `beta`, `r2` |
| `daily_series.csv` | trading day and instrument (5,528 rows) | `trade_date`, `ticker`, `regime`, `growth_index`, `drawdown_pct`, `rolling_sharpe_252` |
| `period_metrics.csv` | period, instrument, basis (35 rows) | `period`, `period_order`, `ticker`, `basis`, `cum_return_pct`, `ann_return_pct`, `ann_vol_pct`, `sharpe`, `sharpe_ci_low`, `sharpe_ci_high`, `mdd_pct` |
| `sharpe_difference.csv` | period and bank (12 rows) | `period`, `period_order`, `ticker`, `delta`, `ci_low`, `ci_high`, `p_value`, `p_holm`, `significant_5pct`, `label` |
| `capm.csv` | period and bank (12 rows) | `beta`, `beta_ci_low`, `beta_ci_high`, `p_beta_eq_1`, `p_beta_eq_1_holm`, `r2`, `r2_ci_low`, `r2_ci_high`, `alpha_ann_pct`, `alpha_p` |
| `market_implied.csv` | period and bank (12 rows) | `beta`, `ihsg_return_pct`, `actual_pct`, `market_implied_pct`, `gap_pct_points` |
| `regimes.csv` | regime (4 rows) | `regime`, `label`, `start_date`, `end_date`, `return_days` |

The extracts are derived from Yahoo Finance prices. They are excluded from git. Do not publish them, or a packaged workbook (`.twbx`) or a Tableau Public workbook that contains them, without checking the provider's terms (see section 8).

## 3. Rules that keep Tableau consistent with the analysis

1. **Never recompute a metric in Tableau.** Every value is precomputed and validated. Do not use Tableau's own running totals, table calculations or quick calculations for returns, Sharpe ratios, drawdowns or betas.
2. **Turn off aggregation on every sheet:** *Analysis > Aggregate Measures* (unchecked). Each row then becomes one mark. With aggregation on, removing a dimension from a sheet silently *sums* values such as Sharpe ratios across periods, which is meaningless.
3. **No date-range filter on the daily charts.** The growth index and drawdowns are measured from the 30 December 2020 close; filtering the dates would cut the lines without rebasing them and would misstate returns. Use the regime reference lines instead.
4. **Percent fields are already in percent.** `cum_return_pct = -10.27` means −10.27%. Format them as *Number (Custom)* with 2 decimals and the suffix `%`; do **not** use Tableau's *Percentage* format, which multiplies by 100.
5. **Single-value filters only.** Where a sheet uses `basis` or `period`, make the filter single-value (dropdown), so two bases or two periods are never mixed in one mark.
6. **Sort periods by `period_order`,** not alphabetically (Full, R1, R2, R3, Stub).

## 4. Style

| Item | Setting |
|---|---|
| Colours (fixed per instrument, never reassigned) | BBCA `#2a78d6`, BBRI `#eb6834`, BMRI `#1baf7a`, IHSG `#52514e` |
| IHSG line | grey and, where your version allows, dashed (*Marks > Path > Line Pattern*, Tableau 2023.2 or later); otherwise solid grey |
| Text | dark ink for values and labels (not the series colour); muted grey `#52514e` for captions and axes |
| Gridlines | light, horizontal only; no vertical gridlines; no chart borders |
| Line width | thin (about 1.5 to 2 px); markers about 8 px on dot charts |
| Font | Tableau Book / Tableau Regular throughout |
| Legend | one shared colour legend for the instrument; on the line charts also label the line ends |

## 5. Sheets

### S1. Headline tiles (`kpi.csv`)
- *Rows:* `ticker` (order BBCA, BBRI, BMRI, IHSG). *Columns:* Measure Names. *Text:* Measure Values.
- Keep these measures, renamed: **Price return 2021–26** (`price_return_pct`), **Total return incl. dividends** (`total_return_pct`), **Sharpe ratio** (`sharpe`), **Sharpe minus IHSG** (`sharpe_diff_vs_ihsg`), **p-value** (`sharpe_diff_p`), **Beta** (`beta`), **R²** (`r2`).
- IHSG has no total return, difference, beta or R²: show the empty cells as "–" (*Format > Pane > Special Values > Text*).
- Tooltip: "Full period, 4 Jan 2021 – 30 Sep 2026. Sharpe ratio on excess returns over the BI policy rate, annualized with √252. The difference from the IHSG is tested with the Ledoit–Wolf paired bootstrap."

### S2. Growth of 100 (`daily_series.csv`)
- Marks: Line. *Columns:* `trade_date` (continuous, *Exact Date*). *Rows:* `growth_index`. *Colour:* `ticker`.
- Reference lines (*Analytics > Reference Line > Table*, Value = Constant date, label = the regime name): **R2** at 2022-08-23, **R3** at 2024-09-18, **Stub** at 2026-05-20. Thin grey, dotted. Also a constant line at 100.
- Label line ends (*Label > Line Ends*, end only): `ticker` and `growth_index` with no decimals.
- Title: "Growth of 100 invested on 30 December 2020 (price return)".
- Tooltip: "<ticker>, <trade_date>: <growth_index> (<regime>)".

### S3. Sharpe ratio minus the IHSG's, with 95% interval (`sharpe_difference.csv`) — the main research question
- *Rows:* `period` (sorted by `period_order`), then `ticker`. *Columns:* `ci_low` and `delta` as a **dual axis** (synchronize the axis).
- First axis: Marks = Gantt Bar, Size = calculated field `CI width = [ci_high] - [ci_low]`. Second axis: Marks = Circle at `delta`. Colour both by `ticker`.
- Reference line: constant 0 on the axis, solid grey.
- Title: "Sharpe ratio of each bank minus the IHSG's (95% interval)". Caption under the chart: "Intervals that cross 0: no significant difference. None of the 12 does."
- Tooltip: "<ticker>, <period>: difference <delta> (95% interval <ci_low> to <ci_high>), p = <p_value>, Holm-adjusted p = <p_holm>".

### S4. Actual return against market-implied return (`market_implied.csv`)
- *Rows:* `period` (sorted, Full, R1, R2, R3), then `ticker`. *Columns:* `gap_pct_points`. Marks: Bar. *Colour:* `ticker`.
- Reference line at 0. Label the bars with `gap_pct_points` (no decimals, "pts").
- Title: "Return not accounted for by market exposure (percentage points)". Caption: "Actual price return minus the return implied by beta × IHSG plus the risk-free rate. R3: about −23 to −29 points; R2: +15 to +66 points."
- Tooltip: "<ticker>, <period>: actual <actual_pct>%, market-implied <market_implied_pct>%, gap <gap_pct_points> points; beta <beta>".

### S5. Beta against the IHSG, with 95% interval (`capm.csv`)
- Same construction as S3, using `beta_ci_low`, `beta_ci_high` and `beta`. Reference line at **1** (dashed): "beta = 1, moves one-for-one with the IHSG".
- Title: "Beta against the IHSG (95% HC3 interval)".
- Tooltip: "<ticker>, <period>: beta <beta> (<beta_ci_low> to <beta_ci_high>); test of beta = 1: p = <p_beta_eq_1>, Holm-adjusted <p_beta_eq_1_holm>".

### Detail sheets (second dashboard)
- **S6 Drawdown** (`daily_series.csv`): as S2 with `drawdown_pct`; title "Drawdown from the running peak (price return)".
- **S7 Rolling 252-day Sharpe ratio** (`daily_series.csv`): as S2 with `rolling_sharpe_252` (the first 251 days are empty by design); reference line at 0.
- **S8 R² with 95% interval** (`capm.csv`): as S3 with `r2_ci_low`, `r2_ci_high`, `r2`; axis fixed 0 to 1. Caption: "R² moves with market volatility as well as with the relationship; read it with beta."
- **S9 Price against total return** (`period_metrics.csv`, banks only): *Columns:* `period`; *Rows:* `cum_return_pct`; side-by-side bars by `basis`; colour by `ticker`. Filter `ticker` to the banks.
- **S10 Regimes** (`regimes.csv`): a small text table of regime, label, dates and return days.

## 6. Dashboards

**Dashboard 1, "Overview"** (fixed size 1200 × 800):

```
+--------------------------------------------------------------------------------+
| TITLE                                                                          |
| Subtitle (finding)                                                             |
| Context line (period, returns, benchmark, annualization, source)              |
+--------------------------------------------------------------------------------+
| S1 headline tiles                                                              |
+-----------------------------------------------+--------------------------------+
| S2 Growth of 100                              | S3 Sharpe minus IHSG           |
|                                               | (main research question)       |
+-----------------------------------------------+--------------------------------+
| S4 Return not accounted for by market         | S5 Beta against the IHSG       |
+-----------------------------------------------+--------------------------------+
| Footer: limitations                                                            |
+--------------------------------------------------------------------------------+
```

**Dashboard 2, "Detail"** (same size): S6 and S7 on top, S8 and S9 below, S10 at the side. Navigation buttons between the two dashboards (*Objects > Navigation*).

**Interaction.** One action only: *Dashboard > Actions > Add Action > Highlight*, source = all sheets, run on Hover, target field = `ticker`. Hovering an instrument highlights it everywhere. No filters across sheets.

**Text (use exactly).**
- Title: **Indonesia's Big Three banks against the IHSG, 2021–2026**
- Subtitle: **No bank's risk-adjusted return is statistically distinguishable from the IHSG's. The banks diverged most in the 2024–26 easing regime, losing about 43% against 19% for the index.**
- Context line: *BBCA, BBRI, BMRI against the IHSG · daily price returns, 4 January 2021 – 30 September 2026 · excess returns over the Bank Indonesia policy rate · annualized with 252 trading days · Source: Yahoo Finance (yfinance), Bank Indonesia; own calculations*
- Footer: *Historical and in-sample; not a forecast or investment advice. Price returns exclude dividends (the IHSG data has none); all returns in rupiah, no currency adjustment. The banks are part of the IHSG, so beta and R² are partly mechanical. Regime dates: R1 to 22 Aug 2022, R2 to 17 Sep 2024, R3 to 19 May 2026, Stub to 30 Sep 2026. Full method and limitations: report/report_draft.md.*

## 7. Validation checklist

Check each value on the finished dashboard against this list (the values come from the validated real-data results; they are what the extracts contain). Hover the marks or use *View Data* on a sheet. A mismatch almost always means aggregation is on, a filter is multi-value, or a percent field was formatted as a percentage.

**S1 headline tiles**

| Ticker | Price return | Total return | Sharpe | Sharpe minus IHSG | p | Beta | R² |
|---|---|---|---|---|---|---|---|
| BBCA | −10.27% | +6.95% | −0.15 | +0.05 | 0.90 | 0.94 | 0.38 |
| BBRI | −17.17% | +19.25% | −0.13 | +0.06 | 0.86 | 1.14 | 0.40 |
| BMRI | +26.80% | +88.39% | 0.13 | +0.33 | 0.39 | 1.17 | 0.40 |
| IHSG | +1.54% | – | −0.20 | – | – | – | – |

**S2 growth of 100, last day (30 Sep 2026):** BBCA 89.7, BBRI 82.8, BMRI 126.8, IHSG 101.5. **S6 drawdown minimum (8 Jun 2026):** BBCA −55.71%, BBRI −59.53%, BMRI −50.20%, IHSG −41.52%. **S7 rolling Sharpe:** first value on 7 Jan 2022; last day −0.74, −0.85, −0.33, −1.08.

**S3 Sharpe minus IHSG (95% interval, p)**

| Period | BBCA | BBRI | BMRI |
|---|---|---|---|
| Full | +0.05 (−0.69 to 0.79), 0.90 | +0.06 (−0.66 to 0.79), 0.86 | +0.33 (−0.44 to 1.10), 0.39 |
| R1 | −0.19 (−1.58 to 1.20), 0.79 | −0.32 (−1.55 to 0.91), 0.60 | +0.07 (−1.37 to 1.50), 0.93 |
| R2 | +0.53 (−0.61 to 1.66), 0.36 | +0.35 (−0.88 to 1.59), 0.57 | +1.00 (−0.27 to 2.28), 0.12 |
| R3 | −0.54 (−2.16 to 1.08), 0.50 | −0.26 (−1.77 to 1.26), 0.73 | −0.25 (−1.81 to 1.30), 0.73 |

**S4 gap (percentage points)**

| Period | BBCA | BBRI | BMRI |
|---|---|---|---|
| Full | −13.94 | −13.94 | +31.02 |
| R1 | −1.39 | −10.19 | +12.19 |
| R2 | +20.94 | +15.15 | +65.58 |
| R3 | −29.37 | −22.99 | −24.15 |

**S5 beta (95% interval)**

| Period | BBCA | BBRI | BMRI |
|---|---|---|---|
| Full | 0.94 (0.84 to 1.03) | 1.14 (1.04 to 1.24) | 1.17 (1.07 to 1.27) |
| R1 | 1.06 (0.88 to 1.23) | 1.34 (1.16 to 1.51) | 1.32 (1.12 to 1.51) |
| R2 | 0.96 (0.80 to 1.11) | 1.36 (1.17 to 1.54) | 1.45 (1.24 to 1.65) |
| R3 | 0.82 (0.67 to 0.98) | 1.04 (0.87 to 1.21) | 1.06 (0.88 to 1.24) |

**S8 R² (95% interval):** Full 0.38 (0.30–0.45), 0.40 (0.34–0.47), 0.40 (0.34–0.46); R2 0.28 (0.21–0.34), 0.36 (0.28–0.43), 0.36 (0.29–0.42).

**Labels present** (required on every published view): analysis period, return frequency and convention (daily, price, excess over the policy rate), benchmark (IHSG), annualization (252), data source, limitations. Tick each one on the finished dashboard.

Record the result of the check (date, Tableau version, any fixes) at the end of this file.

## 8. Publishing

This project is built with **Tableau Desktop Free Edition**, which cannot publish to Tableau Public (Tableau help: "You can't save to Tableau Public with Tableau Desktop Free Edition"). The dashboard is therefore shared as the workbook file (`bank_dashboard_final.twb`, which is in the repository and contains no data) plus exported images. The data extracts stay on the local machine.

- **Save** the workbook locally (check the formats offered under *File > Save As*; a packaged `.twbx` includes the data).
- **Export** the two dashboards as PNG images (*Dashboard > Export Image*) into `reports/figures/` (tracked by git), as `dashboard_overview.png` and `dashboard_detail.png`. These images go into the README and the report (section 8.8). They show aggregated, derived results only.
- Do not put the extracts, or a workbook file that contains them, in the GitHub repository unless the data provider's terms allow redistribution. `tableau/data/` is already excluded by `.gitignore`.
- If the project later moves to Tableau Public (Desktop Public Edition), remember that everything published there is public, including the data inside the workbook.

## Validation record

**Date:** 2026-10-20. **Tableau:** Desktop Free Edition 2026.2. **Workbook:** `tableau/bank_dashboard_final.twb`, generated by `build_workbook.py`, then finished by hand. Rerunning the generator writes `bank_dashboard.twb` and does not overwrite the finished file. **Exports:** `reports/figures/dashboard_overview.png` and `dashboard_detail.png` (1200 × 800).

**Section 7 checks.** All passed.
- **S1 headline tiles:** all 27 values read from the exported image match the table.
- **Hover-level values,** checked against the extracts the workbook reads:
  - S2 last day: 89.73 / 82.83 / 126.80 / 101.54.
  - S6 minimums on 8 Jun 2026: −55.71 / −59.53 / −50.20 / −41.52.
  - S7 first value on 7 Jan 2022; last day −0.74 / −0.85 / −0.33 / −1.08.
  - S3: all 12 differences, intervals and p-values.
  - S4: all 12 gaps.
  - S5 and S8: betas and R² with intervals.
- **Visual positions on the exported charts** agree with these values, for example:
  - S3: BMRI R2 about +1.0.
  - S4: BMRI R2 about +66, R3 bars between −23 and −29.
  - S5: BMRI R2 about 1.45.
  - S8: BBCA R2 about 0.28.
- **Labels:**
  - The period, return convention, benchmark, annualization and source are in the context line.
  - The limitations are in the footer.

**Fixes made during the build:**
- **Schema and loading errors:** fixed in the generator. These were missing windows and viewpoints, element order, and layout attributes.
- **S10 dates:** start and end dates typed as text, because date-typed row labels were dropped.
- **Regime lines on S2:** three constant date reference lines labelled R2, R3 and Stub. Tableau rejected date-parameter lines.
- **Hidden headers:** Show Header turned off on Instrument, not Period, on S3, S4, S5 and S8.
- **S9:** return basis moved to rows, with the Instrument header hidden.
- **S10:** laid out across columns.
- **S7:** null values filtered out, which removes the ">1K nulls" badge.
- **Bank colours:** set by hand.

**Cosmetic fixes (same day):**
- **Axis titles:** S3 reads "Sharpe ratio minus IHSG", S5 "Beta" and S8 "R-squared". Before, each axis showed the field name of the interval's lower end.
- **Date axes:** the "Day of Date" title is removed on S2, S6 and S7.
- **Legends:** taller on both pages, so all four instruments show.
- **S2 subtitle:** now reads "Vertical lines".
- **Header text boxes:**
  - Made taller, so the context line (period, convention, annualization, source) is no longer cut off.
  - On the Overview page, the headline is shortened to one line: banks about −43% against −18.66% for the IHSG in R3, shown as −19%.
- **Re-export:** both PNGs were re-exported after these fixes (2026-10-20). Checked: every value is unchanged and all labels are visible.

**Still truncated (column and row header labels only, no values affected):**
- "Instrume.." and "Total return incl. div.." on S1.
- "Return b.." and "Cumulati.." on S9.
- "Rolling 252-day Shar.." on S7.

**Data Guide outlier note:** Tableau's Data Guide flags BMRI's Sharpe ratio (0.13) and price return (+26.80%) as outliers. Both are the correct values. With four instruments the flag only means BMRI differs from the other three. The difference from the IHSG is not significant (p = 0.39).
