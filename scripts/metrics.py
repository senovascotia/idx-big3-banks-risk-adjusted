"""Metric formulas M1 to M9 from metric_definitions.md, and the H3 Sharpe-difference test.

Pure functions on pandas/numpy objects: no database access, no plotting. Notebooks load
the data with db_access.py and call these functions, so each formula exists in one place.
Inputs are daily simple returns (or prices) indexed by trade date. Nothing is forward-filled.

Conventions (metric_definitions.md, Global conventions and Decisions):
  - 252 trading days for volatility, Sharpe and the daily risk-free divisor.
  - Sample standard deviation (ddof = 1).
  - Annualized return uses calendar-time compounding (365.25 days).
"""
import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252
CALENDAR_DAYS = 365.25

# Regime start and end dates (inclusive), assigned by the return's own trade date.
REGIME_BOUNDS = {
    "R1": (pd.Timestamp("2021-01-01"), pd.Timestamp("2022-08-22")),
    "R2": (pd.Timestamp("2022-08-23"), pd.Timestamp("2024-09-17")),
    "R3": (pd.Timestamp("2024-09-18"), pd.Timestamp("2026-05-19")),
    "Stub": (pd.Timestamp("2026-05-20"), pd.Timestamp("2026-09-30")),
}


# --- M1, M2, M3: returns -------------------------------------------------------------

def simple_returns(prices, first_return_day=None):
    """M1: r_t = P_t / P_(t-1) - 1.

    pct_change() runs on the full price history first and the first return day is applied
    afterwards, so the first return uses the correct prior close (same design as the SQL view).
    """
    r = prices.pct_change()
    return r.loc[first_return_day:] if first_return_day is not None else r.iloc[1:]


def cumulative_return(returns):
    """M2: CR = prod(1 + r_t) - 1 over the return days."""
    return (1 + returns).prod() - 1


def annualized_return(cum_return, calendar_days):
    """M3: AR = (1 + CR) ** (365.25 / D) - 1, D = calendar days from the prior close to the last date."""
    return (1 + cum_return) ** (CALENDAR_DAYS / calendar_days) - 1


def annualized_return_trading(cum_return, n_days):
    """M3 sensitivity: AR = (1 + CR) ** (252 / n) - 1, n = return days."""
    return (1 + cum_return) ** (TRADING_DAYS / n_days) - 1


# --- M4: volatility ------------------------------------------------------------------

def annualized_volatility(returns):
    """M4: sample standard deviation of daily returns times sqrt(252)."""
    return returns.std(ddof=1) * np.sqrt(TRADING_DAYS)


# --- M5: risk-free rate and excess return --------------------------------------------

def daily_risk_free(rate_pct):
    """M5: rf_t = BI rate (percent) / 100 / 252."""
    return rate_pct / 100 / TRADING_DAYS


def excess_return(returns, rf_daily):
    """M5: e_t = r_t - rf_t. Both inputs must be indexed by the same trade dates."""
    return returns.sub(rf_daily, axis=0) if isinstance(returns, pd.DataFrame) else returns - rf_daily


# --- M6: Sharpe ratio ----------------------------------------------------------------

def sharpe_ratio(excess, annualize=True):
    """M6: SR = mean(e) / stdev(e); annualized SR_ann = SR * sqrt(252)."""
    sr = excess.mean() / excess.std(ddof=1)
    return sr * np.sqrt(TRADING_DAYS) if annualize else sr


def rolling_sharpe(excess, window=TRADING_DAYS, annualize=True):
    """M6: Sharpe over a rolling window of exactly `window` return days.

    The first value sits on the `window`-th return day (min_periods = window).
    """
    roll = excess.rolling(window, min_periods=window)
    sr = roll.mean() / roll.std(ddof=1)
    return sr * np.sqrt(TRADING_DAYS) if annualize else sr


def lo_sharpe_se(excess, annualize=True):
    """M6: Lo (2002) asymptotic standard error of the Sharpe ratio, i.i.d. case.

    SE(SR) = sqrt((1 + SR**2 / 2) / n) for the per-day ratio; times sqrt(252) when annualized.
    This ignores serial correlation, which Lo (2002) shows can change the scaling; the
    block bootstrap below is the interval actually reported, this is for comparison.
    """
    n = excess.count()
    sr = sharpe_ratio(excess, annualize=False)
    se = np.sqrt((1 + sr ** 2 / 2) / n)
    return se * np.sqrt(TRADING_DAYS) if annualize else se


def stationary_bootstrap_indices(n, n_boot=10_000, block=10, seed=0):
    """Politis-Romano stationary bootstrap: an (n_boot, n) array of row positions.

    Each replicate is built from blocks of geometric length (mean `block`). A new block
    starts at a random position with probability 1 / block, otherwise the previous position
    plus one (wrapping around). Use the same index array for every column of a table so the
    days stay paired across instruments. Fixed seed makes the result reproducible.
    """
    rng = np.random.default_rng(seed)
    idx = np.empty((n_boot, n), dtype=np.int32)
    idx[:, 0] = rng.integers(0, n, n_boot)
    new_block = rng.random((n_boot, n)) < 1.0 / block
    starts = rng.integers(0, n, (n_boot, n))
    for t in range(1, n):
        idx[:, t] = np.where(new_block[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def bootstrap_sharpe_ci(excess, n_boot=10_000, block=10, seed=0, level=0.95, annualize=True):
    """M6: percentile interval for the Sharpe ratio from the stationary block bootstrap.

    Returns (low, high, replicates). Descriptive only; no test of Sharpe differences.
    """
    x = np.asarray(excess, dtype=float)
    x = x[~np.isnan(x)]
    idx = stationary_bootstrap_indices(len(x), n_boot, block, seed)
    sample = x[idx]
    sr = sample.mean(axis=1) / sample.std(axis=1, ddof=1)
    if annualize:
        sr = sr * np.sqrt(TRADING_DAYS)
    tail = (1 - level) / 2
    low, high = np.quantile(sr, [tail, 1 - tail])
    return low, high, sr


def _sharpe_diff(v):
    """Ledoit-Wolf (2008) eq. 2: f(a, b, c, d) = a / sqrt(c - a^2) - b / sqrt(d - b^2).

    v holds (mean_i, mean_n, second moment_i, second moment_n) in its last axis.
    """
    a, b, c, d = v[..., 0], v[..., 1], v[..., 2], v[..., 3]
    return a / np.sqrt(c - a ** 2) - b / np.sqrt(d - b ** 2)


def _sharpe_diff_gradient(v):
    """Gradient of _sharpe_diff (Ledoit-Wolf 2008, below eq. 4)."""
    a, b, c, d = v[..., 0], v[..., 1], v[..., 2], v[..., 3]
    vi, vn = (c - a ** 2) ** 1.5, (d - b ** 2) ** 1.5
    return np.stack([c / vi, -d / vn, -a / (2 * vi), b / (2 * vn)], axis=-1)


def hac_bartlett(centered, lags):
    """Bartlett-kernel (Newey-West) long-run covariance of an already centred (T, k) array."""
    T = len(centered)
    psi = centered.T @ centered / T
    for j in range(1, lags + 1):
        gamma = centered[j:].T @ centered[:-j] / T
        psi += (1 - j / (lags + 1)) * (gamma + gamma.T)
    return psi


def ledoit_wolf_sharpe_test(excess_i, excess_n, block=10, n_boot=10_000, seed=0, level=0.95, lags=None, chunk=500):
    """H3: Ledoit and Wolf (2008) test of equal Sharpe ratios, Sharpe(i) - Sharpe(n) = 0.

    Studentized circular block bootstrap of the paired days (section 3.2.2 of the paper):
      - delta = f(mean_i, mean_n, E[e_i^2], E[e_n^2]); its standard error comes from the delta
        method with a HAC estimate of the moments' long-run covariance, times T / (T - 4).
      - each resample takes whole blocks of `block` consecutive days, wrapping around the end, for
        both series at once; its standard error uses the block sums (Goetze-Kuensch).
      - interval: delta +/- q * se, q = `level` quantile of |delta* - delta| / se*.
      - p-value (Remark 3.2): (#{d* >= d} + 1) / (n_boot + 1), d = |delta| / se.
    Two simplifications against the paper: a Bartlett kernel with the Newey-West lag rule
    instead of the prewhitened quadratic-spectral kernel, and a fixed block size instead of the
    calibration of Algorithm 3.1. Sharpe ratios here use population moments (divide by T), as in
    the paper; they differ from sharpe_ratio() by the factor sqrt(T / (T - 1)).
    Returns annualized values (times sqrt(252)); the test itself does not depend on the scaling.
    """
    df = pd.concat([excess_i, excess_n], axis=1, join="inner").dropna()
    x, y = df.iloc[:, 0].to_numpy(float), df.iloc[:, 1].to_numpy(float)
    T = len(x)
    if lags is None:
        lags = int(np.floor(4 * (T / 100) ** (2 / 9)))
    Y = np.column_stack([x, y, x ** 2, y ** 2])
    v = Y.mean(axis=0)
    delta = _sharpe_diff(v)
    grad = _sharpe_diff_gradient(v)
    psi = hac_bartlett(Y - v, lags) * T / (T - 4)
    se = np.sqrt(grad @ psi @ grad / T)
    d = abs(delta) / se

    rng = np.random.default_rng(seed)
    n_blocks, l = -(-T // block), T // block
    offsets = np.arange(block)
    d_star = np.empty(n_boot)
    for start in range(0, n_boot, chunk):
        m = min(chunk, n_boot - start)
        idx = ((rng.integers(0, T, (m, n_blocks))[..., None] + offsets) % T).reshape(m, -1)[:, :T]
        Ys = Y[idx]
        vs = Ys.mean(axis=1)
        zeta = (Ys[:, :l * block] - vs[:, None, :]).reshape(m, l, block, 4).sum(axis=2) / np.sqrt(block)
        psi_s = np.einsum("mjk,mjn->mkn", zeta, zeta) / l
        gs = _sharpe_diff_gradient(vs)
        se_s = np.sqrt(np.einsum("mk,mkn,mn->m", gs, psi_s, gs) / T)
        d_star[start:start + m] = np.abs(_sharpe_diff(vs) - delta) / se_s

    q = np.quantile(d_star, level)
    ann = np.sqrt(TRADING_DAYS)
    return {
        "sharpe_i": ann * v[0] / np.sqrt(v[2] - v[0] ** 2),
        "sharpe_n": ann * v[1] / np.sqrt(v[3] - v[1] ** 2),
        "delta": ann * delta, "se": ann * se,
        "ci_low": ann * (delta - q * se), "ci_high": ann * (delta + q * se),
        "p_value": (np.sum(d_star >= d) + 1) / (n_boot + 1),
        "p_hac_normal": 2 * (1 - _normal_cdf(d)),
        "d": d, "n": T, "block": block, "lags": lags, "n_boot": n_boot,
    }


def _normal_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# --- M7, M8: CAPM and Dimson beta ----------------------------------------------------

def capm(excess_asset, excess_market):
    """M7: OLS of e_i on e_m. Returns alpha (daily), beta, R-squared and n.

    Point estimates only (closed form). HC3 standard errors, the t-test of beta = 1 and the
    Ljung-Box test are computed in notebook 03 with statsmodels.
    """
    df = pd.concat([excess_asset, excess_market], axis=1, join="inner").dropna()
    y = df.iloc[:, 0].to_numpy()
    x = df.iloc[:, 1].to_numpy()
    beta = np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1)
    alpha = y.mean() - beta * x.mean()
    resid = y - alpha - beta * x
    r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return {"alpha": alpha, "beta": beta, "r2": r2, "n": len(df)}


def r2_from_indices(excess_asset, excess_market, idx):
    """M7: R-squared of the simple regression for every bootstrap replicate.

    `idx` is an (n_boot, n) array of row positions from stationary_bootstrap_indices(), built
    for the same n. In a one-regressor OLS with an intercept, R-squared is the squared
    correlation, so each replicate is computed in closed form (no regression loop).
    """
    df = pd.concat([excess_asset, excess_market], axis=1, join="inner").dropna()
    y = df.iloc[:, 0].to_numpy()[idx]
    x = df.iloc[:, 1].to_numpy()[idx]
    y = y - y.mean(axis=1, keepdims=True)
    x = x - x.mean(axis=1, keepdims=True)
    r = (x * y).sum(axis=1) / np.sqrt((x ** 2).sum(axis=1) * (y ** 2).sum(axis=1))
    return r ** 2


def dimson_beta(excess_asset, excess_market, lags=1, leads=1):
    """M8: Dimson (1979) beta = sum of slopes on e_m at lags -`lags` .. +`leads`.

    With lags = leads = 0 this reproduces capm(). The first `lags` and last `leads` days
    are lost to the shifts. Returns the summed beta, each slope and n.
    """
    cols = {}
    for k in range(-lags, leads + 1):
        cols[k] = excess_market.shift(-k)  # k = +1 is the next day's market return
    X = pd.DataFrame(cols)
    df = pd.concat([excess_asset.rename("y"), X], axis=1, join="inner").dropna()
    y = df["y"].to_numpy()
    A = np.column_stack([np.ones(len(df)), df[list(cols)].to_numpy()])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    slopes = dict(zip(cols, coef[1:]))
    return {"beta": coef[1:].sum(), "slopes": slopes, "alpha": coef[0], "n": len(df)}


# --- M9: drawdown --------------------------------------------------------------------

def drawdown_series(prices):
    """Drawdown at each date: P_t / running max of P - 1."""
    return prices / prices.cummax() - 1


def max_drawdown(prices):
    """M9: maximum drawdown with peak, trough and recovery dates for one price series.

    The running maximum starts at the first price given, so slice the series to a regime
    before calling to reset it. recovery_date is None when the peak is not regained.
    """
    prices = prices.dropna()
    dd = drawdown_series(prices)
    trough = dd.idxmin()
    peak = prices.loc[:trough].idxmax()
    after = prices.loc[trough:]
    regained = after[after >= prices.loc[peak]]
    recovery = regained.index[0] if len(regained) else None
    return {"mdd": dd.loc[trough], "peak_date": peak, "trough_date": trough, "recovery_date": recovery}


# --- Regimes -------------------------------------------------------------------------

def assign_regime(index):
    """Label each trade date R1, R2, R3 or Stub (by the return's own date)."""
    labels = pd.Series(pd.NA, index=index, dtype="object")
    for name, (start, end) in REGIME_BOUNDS.items():
        labels[(index >= start) & (index <= end)] = name
    return labels


def regime_slices(frame):
    """Split a date-indexed frame into {regime: rows}. Dates outside every regime are dropped."""
    labels = assign_regime(frame.index)
    return {name: frame[labels == name] for name in REGIME_BOUNDS}
