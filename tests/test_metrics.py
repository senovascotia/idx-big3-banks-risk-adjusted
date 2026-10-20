"""Hand-made checks of scripts/metrics.py (offline: no database).

Every expected value is worked out by hand in the comment next to it, so a reader can redo the
arithmetic with a pencil. Run from the project root:

    python -I tests/test_metrics.py
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import metrics

SQRT252 = math.sqrt(252)


def dates(n, start="2021-01-04"):
    return pd.bdate_range(start, periods=n)


class TestReturns(unittest.TestCase):
    def test_simple_returns(self):
        # 110/100 - 1 = +0.10; 99/110 - 1 = -0.10; 108.9/99 - 1 = +0.10
        p = pd.Series([100, 110, 99, 108.9], index=dates(4, "2020-12-30"))
        r = metrics.simple_returns(p, pd.Timestamp("2020-12-31"))
        np.testing.assert_allclose(r.to_numpy(), [0.10, -0.10, 0.10], atol=1e-12)

    def test_first_return_uses_the_prior_close(self):
        # the first return day is the 2nd date, so its return is 110 / 100 - 1, not NaN
        p = pd.Series([100, 110, 121], index=dates(3, "2020-12-30"))
        r = metrics.simple_returns(p, p.index[1])
        self.assertAlmostEqual(r.iloc[0], 0.10, places=12)
        self.assertEqual(len(r), 2)

    def test_cumulative_return_equals_the_price_ratio(self):
        # 1.10 * 0.90 * 1.10 = 1.089, and 108.9 / 100 = 1.089
        p = pd.Series([100, 110, 99, 108.9], index=dates(4, "2020-12-30"))
        r = metrics.simple_returns(p, pd.Timestamp("2020-12-31"))
        self.assertAlmostEqual(metrics.cumulative_return(r), 108.9 / 100 - 1, places=12)
        self.assertAlmostEqual(metrics.cumulative_return(r), 0.089, places=12)

    def test_annualized_return(self):
        # one calendar year (365.25 days): AR = CR
        self.assertAlmostEqual(metrics.annualized_return(0.20, 365.25), 0.20, places=12)
        # two years: 1.2 ** (1 / 2) - 1 = 0.0954451...
        self.assertAlmostEqual(metrics.annualized_return(0.20, 730.5), math.sqrt(1.2) - 1, places=12)
        # 504 trading days = 2 years of 252: 1.44 ** (252 / 504) - 1 = 1.2 - 1 = 0.20
        self.assertAlmostEqual(metrics.annualized_return_trading(0.44, 504), 0.20, places=12)


class TestVolatilitySharpe(unittest.TestCase):
    def test_volatility(self):
        # returns +1%, -1%, +1%, -1%: mean 0; sum of squares 4 * 0.0001; sample variance = 0.0004 / 3
        r = pd.Series([0.01, -0.01, 0.01, -0.01], index=dates(4))
        expected = math.sqrt(0.0004 / 3) * SQRT252
        self.assertAlmostEqual(metrics.annualized_volatility(r), expected, places=12)
        self.assertAlmostEqual(metrics.annualized_volatility(r), 0.18330, places=4)

    def test_risk_free_and_excess_return(self):
        # 3.5 / 100 / 252 = 0.000138888...; excess = 0.01 - 0.001
        self.assertAlmostEqual(metrics.daily_risk_free(3.5), 0.035 / 252, places=15)
        r = pd.Series([0.01, 0.02], index=dates(2))
        e = metrics.excess_return(r, pd.Series([0.001, 0.002], index=r.index))
        np.testing.assert_allclose(e.to_numpy(), [0.009, 0.018], atol=1e-15)

    def test_sharpe_on_a_20_day_sample(self):
        # 10 days at +2% and 10 days at 0: mean 0.01; each deviation is +/-0.01, so the sum of
        # squares is 20 * 0.0001 and the sample variance 0.002 / 19. The daily ratio is
        # 0.01 / sqrt(0.002 / 19) = sqrt(19 / 20) = 0.974679; annualized x sqrt(252) = 15.4725
        e = pd.Series([0.02] * 10 + [0.0] * 10, index=dates(20))
        self.assertAlmostEqual(metrics.sharpe_ratio(e, annualize=False), math.sqrt(19 / 20), places=12)
        self.assertAlmostEqual(metrics.sharpe_ratio(e), math.sqrt(19 / 20) * SQRT252, places=10)
        self.assertAlmostEqual(metrics.sharpe_ratio(e), 15.4725, places=3)

    def test_rolling_sharpe_window(self):
        rng = np.random.default_rng(3)
        e = pd.Series(rng.normal(0.0005, 0.01, 400), index=dates(400))
        rs = metrics.rolling_sharpe(e, window=252)
        # the first value is on the 252nd day (position 251) and nothing exists before it
        self.assertEqual(rs.first_valid_index(), e.index[251])
        self.assertTrue(rs.iloc[:251].isna().all())
        # the value at position 300 uses exactly the 252 days at positions 49 to 300
        self.assertAlmostEqual(rs.iloc[300], metrics.sharpe_ratio(e.iloc[49:301]), places=12)
        self.assertNotAlmostEqual(rs.iloc[300], metrics.sharpe_ratio(e.iloc[50:301]), places=6)

    def test_lo_standard_error(self):
        # mean exactly 0 gives SR = 0, so SE = sqrt(1 / n) per day = 0.1 for n = 100;
        # annualized = 0.1 * sqrt(252) = 1.58745
        e = pd.Series([1.0, -1.0] * 50, index=dates(100))
        self.assertAlmostEqual(metrics.lo_sharpe_se(e, annualize=False), 0.1, places=12)
        self.assertAlmostEqual(metrics.lo_sharpe_se(e), 0.1 * SQRT252, places=12)


class TestBootstrap(unittest.TestCase):
    def test_indices_are_valid_and_reproducible(self):
        a = metrics.stationary_bootstrap_indices(50, 200, 10, seed=1)
        b = metrics.stationary_bootstrap_indices(50, 200, 10, seed=1)
        self.assertEqual(a.shape, (200, 50))
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(a.min() >= 0 and a.max() < 50)
        self.assertFalse(np.array_equal(a, metrics.stationary_bootstrap_indices(50, 200, 10, seed=2)))

    def test_mean_block_length(self):
        # a block continues with probability 1 - 1 / block, so about 90% of steps for block = 10
        idx = metrics.stationary_bootstrap_indices(500, 200, 10, seed=3).astype(int)
        continue_share = ((np.diff(idx, axis=1) % 500) == 1).mean()
        self.assertAlmostEqual(continue_share, 0.9, delta=0.03)

    def test_sharpe_interval_brackets_the_estimate(self):
        rng = np.random.default_rng(4)
        e = pd.Series(rng.normal(0.001, 0.01, 300), index=dates(300))
        low, high, reps = metrics.bootstrap_sharpe_ci(e, n_boot=1000, block=10, seed=5)
        self.assertLess(low, metrics.sharpe_ratio(e))
        self.assertGreater(high, metrics.sharpe_ratio(e))
        self.assertEqual(len(reps), 1000)


class TestSharpeDifference(unittest.TestCase):
    def test_difference_function(self):
        # x: mean 0.02, E[x^2] = 0.0008 -> variance 0.0004, sd 0.02 -> SR 1.0
        # y: mean 0.01, E[y^2] = 0.0005 -> variance 0.0004, sd 0.02 -> SR 0.5; difference 0.5
        v = np.array([0.02, 0.01, 0.0008, 0.0005])
        self.assertAlmostEqual(float(metrics._sharpe_diff(v)), 0.5, places=12)

    def test_gradient_matches_finite_differences(self):
        v = np.array([0.0006, 0.0003, 0.00025, 0.00012])
        grad = metrics._sharpe_diff_gradient(v)
        h = 1e-9
        for k in range(4):
            up, down = v.copy(), v.copy()
            up[k] += h
            down[k] -= h
            numeric = (metrics._sharpe_diff(up) - metrics._sharpe_diff(down)) / (2 * h)
            self.assertAlmostEqual(grad[k] / numeric, 1.0, places=5)

    def test_hac_with_no_lags_is_the_sample_covariance(self):
        rng = np.random.default_rng(7)
        Y = rng.normal(size=(200, 3))
        c = Y - Y.mean(axis=0)
        np.testing.assert_allclose(metrics.hac_bartlett(c, 0), c.T @ c / 200, atol=1e-15)

    def _pair(self, shift):
        rng = np.random.default_rng(8)
        common = rng.normal(0, 0.01, 800)
        x = pd.Series(common + rng.normal(0.0, 0.008, 800) + shift, index=dates(800))
        y = pd.Series(common + rng.normal(0.0, 0.008, 800), index=dates(800))
        return x, y

    def test_detects_a_large_difference(self):
        x, y = self._pair(0.004)
        res = metrics.ledoit_wolf_sharpe_test(x, y, block=10, n_boot=1000, seed=1)
        self.assertLess(res["p_value"], 0.01)
        self.assertGreater(res["ci_low"], 0)
        self.assertTrue(res["ci_low"] < res["delta"] < res["ci_high"])

    def test_no_difference_is_not_rejected(self):
        x, y = self._pair(0.0)
        res = metrics.ledoit_wolf_sharpe_test(x, y, block=10, n_boot=1000, seed=1)
        self.assertGreater(res["p_value"], 0.05)
        self.assertTrue(res["ci_low"] < 0 < res["ci_high"])

    def test_swapping_the_series_flips_the_sign_and_keeps_the_p_value(self):
        x, y = self._pair(0.001)
        a = metrics.ledoit_wolf_sharpe_test(x, y, block=10, n_boot=500, seed=3)
        b = metrics.ledoit_wolf_sharpe_test(y, x, block=10, n_boot=500, seed=3)
        self.assertAlmostEqual(a["delta"], -b["delta"], places=12)
        self.assertAlmostEqual(a["p_value"], b["p_value"], places=12)

    def test_sharpe_ratios_use_population_moments(self):
        # the test's Sharpe ratio = sharpe_ratio() * sqrt(T / (T - 1))
        x, y = self._pair(0.001)
        res = metrics.ledoit_wolf_sharpe_test(x, y, block=10, n_boot=200, seed=3)
        self.assertAlmostEqual(res["sharpe_i"], metrics.sharpe_ratio(x) * math.sqrt(800 / 799), places=10)
        self.assertAlmostEqual(res["delta"], res["sharpe_i"] - res["sharpe_n"], places=12)


class TestCapmDimson(unittest.TestCase):
    X = pd.Series([1.0, 2.0, 3.0, 4.0], index=dates(4))
    Y = pd.Series([2.0, 4.0, 5.0, 9.0], index=dates(4))

    def test_capm_worked_by_hand(self):
        # x mean 2.5, y mean 5; Sxx = 2.25 + 0.25 + 0.25 + 2.25 = 5;
        # Sxy = (-1.5)(-3) + (-0.5)(-1) + (0.5)(0) + (1.5)(4) = 11  ->  beta = 11 / 5 = 2.2
        # alpha = 5 - 2.2 * 2.5 = -0.5; residuals 0.3, 0.1, -1.1, 0.7 -> SSres = 1.80;
        # SStot = 9 + 1 + 0 + 16 = 26  ->  R2 = 1 - 1.8 / 26 = 0.930769
        c = metrics.capm(self.Y, self.X)
        self.assertAlmostEqual(c["beta"], 2.2, places=12)
        self.assertAlmostEqual(c["alpha"], -0.5, places=12)
        self.assertAlmostEqual(c["r2"], 1 - 1.8 / 26, places=12)
        self.assertEqual(c["n"], 4)

    def test_r2_from_indices_matches_the_regression(self):
        ident = np.arange(4)[None, :]
        self.assertAlmostEqual(metrics.r2_from_indices(self.Y, self.X, ident)[0], 1 - 1.8 / 26, places=12)

    def test_perfect_line(self):
        c = metrics.capm(3.0 + 0.5 * self.X, self.X)
        self.assertAlmostEqual(c["beta"], 0.5, places=12)
        self.assertAlmostEqual(c["alpha"], 3.0, places=12)
        self.assertAlmostEqual(c["r2"], 1.0, places=12)

    def test_dimson_recovers_known_slopes(self):
        # y_t = 0.5 x_(t-1) + 1.0 x_t + 0.25 x_(t+1) exactly, so the slopes are 0.5, 1.0, 0.25
        # and the Dimson beta is their sum, 1.75. The first and last day lose one observation.
        rng = np.random.default_rng(6)
        x = pd.Series(rng.normal(0, 0.01, 60), index=dates(60))
        y = 0.5 * x.shift(1) + 1.0 * x + 0.25 * x.shift(-1)
        d = metrics.dimson_beta(y, x)
        self.assertAlmostEqual(d["slopes"][-1], 0.5, places=10)
        self.assertAlmostEqual(d["slopes"][0], 1.0, places=10)
        self.assertAlmostEqual(d["slopes"][1], 0.25, places=10)
        self.assertAlmostEqual(d["beta"], 1.75, places=10)
        self.assertEqual(d["n"], 58)

    def test_dimson_with_no_lags_or_leads_equals_capm(self):
        d = metrics.dimson_beta(self.Y, self.X, lags=0, leads=0)
        self.assertAlmostEqual(d["beta"], metrics.capm(self.Y, self.X)["beta"], places=12)


class TestDrawdown(unittest.TestCase):
    def test_worked_by_hand(self):
        # peak 120, trough 60: 60 / 120 - 1 = -0.50; the peak is regained at 125 (position 5)
        q = pd.Series([100, 120, 90, 60, 80, 125, 130], index=dates(7))
        md = metrics.max_drawdown(q)
        self.assertAlmostEqual(md["mdd"], -0.5, places=12)
        self.assertEqual(md["peak_date"], q.index[1])
        self.assertEqual(md["trough_date"], q.index[3])
        self.assertEqual(md["recovery_date"], q.index[5])

    def test_not_recovered(self):
        q = pd.Series([100, 120, 90, 60, 80], index=dates(5))
        self.assertIsNone(metrics.max_drawdown(q)["recovery_date"])

    def test_the_running_maximum_resets_when_the_series_is_sliced(self):
        # full series: worst drop is 120 -> 60 = -50%. From position 3 on, the path is 60, 80, 70:
        # the running maximum restarts at 60, and the worst drop is 80 -> 70 = -12.5%
        q = pd.Series([100, 120, 90, 60, 80, 70], index=dates(6))
        self.assertAlmostEqual(metrics.max_drawdown(q)["mdd"], -0.5, places=12)
        self.assertAlmostEqual(metrics.max_drawdown(q.iloc[3:])["mdd"], 70 / 80 - 1, places=12)

    def test_drawdown_series(self):
        q = pd.Series([100, 120, 90], index=dates(3))
        np.testing.assert_allclose(metrics.drawdown_series(q).to_numpy(), [0.0, 0.0, 90 / 120 - 1], atol=1e-12)


class TestRegimes(unittest.TestCase):
    def test_boundaries(self):
        d = pd.DatetimeIndex(["2022-08-22", "2022-08-23", "2024-09-17", "2024-09-18",
                              "2026-05-19", "2026-05-20", "2026-09-30"])
        self.assertEqual(list(metrics.assign_regime(d)), ["R1", "R2", "R2", "R3", "R3", "Stub", "Stub"])

    def test_regime_slices_partition_the_rows(self):
        frame = pd.DataFrame({"v": range(7)}, index=pd.DatetimeIndex(
            ["2022-08-22", "2022-08-23", "2024-09-17", "2024-09-18", "2026-05-19", "2026-05-20", "2026-09-30"]))
        parts = metrics.regime_slices(frame)
        self.assertEqual({k: len(v) for k, v in parts.items()}, {"R1": 1, "R2": 2, "R3": 2, "Stub": 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
