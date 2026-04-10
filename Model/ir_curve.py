# IRCurve
# Written by Peter Allen - R&C
# 10 April 2026
# Interest Rate Curve: discount factors, interpolation, forward rates

from __future__ import annotations

import math
from datetime import date
from typing import List

from Utilities.utils import year_fraction


class IRCurve:
    """
    Represents a discounting interest-rate curve defined by a set of
    (date, discount-factor) pillars.

    Parameters
    ----------
    valuation_date       : date
        The "as-of" date of the curve (T=0).
    dates                : list[date]
        Pillar dates, must be strictly increasing and all > valuation_date.
    discount_factors     : list[float]
        Discount factors corresponding to each pillar date.
        Must be the same length as *dates*.
    day_count_convention : str
        Convention used when computing year fractions, e.g. 'ACT/360',
        'ACT/365', '30/360'.  Passed directly to year_fraction().
    interpolation_method : str
        Interpolation method applied to the *zero rates* implied by the
        discount factors.  Supported values:
            'LINEAR_ZERO'    – linear interpolation on zero rates (default)
            'LINEAR_DF'      – linear interpolation on discount factors
            'LOG_LINEAR'     – log-linear interpolation (= flat forward)
    """

    SUPPORTED_INTERPOLATION = ("LINEAR_ZERO", "LINEAR_DF", "LOG_LINEAR")

    def __init__(
        self,
        valuation_date: date,
        dates: List[date],
        discount_factors: List[float],
        day_count_convention: str = "ACT/365",
        interpolation_method: str = "LOG_LINEAR",
    ) -> None:
        if len(dates) != len(discount_factors):
            raise ValueError(
                f"dates (len={len(dates)}) and discount_factors "
                f"(len={len(discount_factors)}) must be the same length."
            )
        if not dates:
            raise ValueError("dates list must not be empty.")

        interp = interpolation_method.strip().upper()
        if interp not in self.SUPPORTED_INTERPOLATION:
            raise ValueError(
                f"Unknown interpolation_method '{interpolation_method}'. "
                f"Supported: {self.SUPPORTED_INTERPOLATION}"
            )

        self.valuation_date = valuation_date
        self.dates: List[date] = list(dates)
        self.discount_factors: List[float] = list(discount_factors)
        self.day_count_convention: str = day_count_convention.strip()
        self.interpolation_method: str = interp

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _t(self, d: date) -> float:
        """Year fraction from valuation_date to *d*."""
        return year_fraction(self.valuation_date, d, self.day_count_convention)

    def _zero_rate(self, t: float, df: float) -> float:
        """Continuously-compounded zero rate from a year fraction and DF."""
        if t <= 0.0 or df <= 0.0:
            return 0.0
        return -math.log(df) / t

    def _interpolate_df(self, target_date: date) -> float:
        """
        Return the interpolated discount factor for *target_date*.
        Flat extrapolation is applied outside the pillar range.
        """
        dates = self.dates
        dfs = self.discount_factors
        t_target = self._t(target_date)

        # --- boundary / exact match ---
        if target_date <= dates[0]:
            return dfs[0]
        if target_date >= dates[-1]:
            return dfs[-1]
        for i, d in enumerate(dates):
            if d == target_date:
                return dfs[i]

        # --- find bracketing pillars ---
        idx = next(i for i, d in enumerate(dates) if d > target_date)
        t1 = self._t(dates[idx - 1])
        t2 = self._t(dates[idx])
        df1, df2 = dfs[idx - 1], dfs[idx]

        if self.interpolation_method == "LINEAR_DF":
            # linear on discount factors
            w = (t_target - t1) / (t2 - t1)
            return df1 + w * (df2 - df1)

        elif self.interpolation_method == "LINEAR_ZERO":
            # linear on continuously-compounded zero rates
            r1 = self._zero_rate(t1, df1)
            r2 = self._zero_rate(t2, df2)
            w = (t_target - t1) / (t2 - t1)
            r = r1 + w * (r2 - r1)
            return math.exp(-r * t_target)

        else:  # LOG_LINEAR (flat forward)
            # log-linear on discount factors
            w = (t_target - t1) / (t2 - t1)
            return math.exp(math.log(df1) + w * (math.log(df2) - math.log(df1)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_disc(self, end_date: date) -> float:
        """
        Return the discount factor from valuation_date to *end_date*.

        Parameters
        ----------
        end_date : date

        Returns
        -------
        float
            Discount factor P(0, end_date).
        """
        if end_date < self.valuation_date:
            raise ValueError(
                f"end_date ({end_date}) must be >= valuation_date ({self.valuation_date})."
            )
        if end_date == self.valuation_date:
            return 1.0
        return self._interpolate_df(end_date)

    def get_forward(self, start_date: date, end_date: date) -> float:
        """
        Return the simply-compounded forward rate between *start_date*
        and *end_date*, consistent with the curve's day count convention.

        Forward rate  f  satisfies:
            P(0, end) = P(0, start) * (1 + f * tau)
        where tau = year_fraction(start, end, convention).

        Parameters
        ----------
        start_date : date
        end_date   : date

        Returns
        -------
        float
            Simply-compounded forward rate.

        Raises
        ------
        ValueError
            If end_date <= start_date, or tau == 0.
        """
        if end_date <= start_date:
            raise ValueError(
                f"end_date ({end_date}) must be strictly after start_date ({start_date})."
            )
        tau = year_fraction(start_date, end_date, self.day_count_convention)
        if tau == 0.0:
            raise ValueError(
                "year_fraction between start_date and end_date is zero; "
                "cannot compute forward rate."
            )
        df_start = self.get_disc(start_date)
        df_end = self.get_disc(end_date)
        return (df_start / df_end - 1.0) / tau
