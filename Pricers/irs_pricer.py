# irs_pricer.py
# Written by Peter Allen - R&C
# 10 April 2026
# IRS NPV pricer for Hedge Effectiveness Calculation

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from Model.ir_curve import IRCurve
from Utilities.cf_parser import FixedCashflow, FloatCashflow
from Utilities.utils import year_fraction


def _price_fixed_leg(
    trade: Dict,
    fixed_cfs: List[FixedCashflow],
    disc_curve: IRCurve,
    value_date: date,
) -> float:
    """
    PV of the fixed leg.

    Each period:
      - Skip entirely if end_date   <= value_date  (period fully elapsed).
      - Skip entirely if payment_date <= value_date (already settled).
      - If start_date < value_date, clamp accrual start to value_date so we
        only accrue the remaining stub of the current period.
      - tau    = year_fraction(accrual_start, end_date)
      - CF     = Notional * FixedRate * tau
      - PV     = CF * DF(payment_date)
    """
    notional   = trade["Notional"]
    fixed_rate = trade["FixedRate"]
    day_count  = trade["DayCount"]
    pv = 0.0

    for cf in fixed_cfs:
        # Fully elapsed or already paid
        if cf.end_date <= value_date:
            continue
        if cf.payment_date <= value_date:
            continue

        # Clamp accrual start to value_date for in-progress periods
        accrual_start = max(cf.start_date, value_date)

        tau    = year_fraction(accrual_start, cf.end_date, day_count)
        coupon = notional * fixed_rate * tau
        df     = disc_curve.get_disc(cf.payment_date)
        pv    += coupon * df

    return pv


def _get_float_rate(
    cf: FloatCashflow,
    fwd_curve: IRCurve,
    fixings: Dict[date, float],
    value_date: date,
) -> float:
    """
    Return the applicable floating rate for a single cashflow period.

    Logic
    -----
    - If reset_date <= value_date  ->  use historical fixing (rate stored in %,
                                       divide by 100 to get decimal).
      - If the reset_date is missing from fixings (e.g. holiday gap), fall back
        to the forward curve using the full period (start_date -> end_date).
    - If reset_date > value_date   ->  use forward curve projection.

    Note: the year-fraction / accrual-start clamping is handled in
    _price_float_leg, not here.  This function returns only the rate.
    """
    if cf.reset_date <= value_date:
        if cf.reset_date in fixings:
            return fixings[cf.reset_date] / 100.0
        # Fixing missing for this date - fall back to forward curve
        return fwd_curve.get_forward(cf.start_date, cf.end_date)
    return fwd_curve.get_forward(cf.start_date, cf.end_date)


def _price_float_leg(
    trade: Dict,
    float_cfs: List[FloatCashflow],
    disc_curve: IRCurve,
    fwd_curve: IRCurve,
    fixings: Dict[date, float],
    value_date: date,
) -> float:
    """
    PV of the floating leg.

    Each period:
      - Skip entirely if end_date    <= value_date  (period fully elapsed).
      - Skip entirely if payment_date <= value_date (already settled).
      - If start_date < value_date, clamp accrual start to value_date so we
        only accrue the remaining stub of the current period.
      - rate   = historical fixing (if reset_date <= value_date) else forward rate
      - tau    = year_fraction(accrual_start, end_date)
      - CF     = Notional * (rate + Spread) * tau
      - PV     = CF * DF(payment_date)

    Spread defaults to 0 if not present in the trade dict.
    """
    notional  = trade["Notional"]
    spread    = trade.get("Spread", 0.0)
    day_count = trade["DayCount"]
    pv = 0.0

    for cf in float_cfs:
        # Fully elapsed or already paid
        if cf.end_date <= value_date:
            continue
        if cf.payment_date <= value_date:
            continue

        # Clamp accrual start to value_date for in-progress periods
        accrual_start = max(cf.start_date, value_date)

        rate   = _get_float_rate(cf, fwd_curve, fixings, value_date)
        tau    = year_fraction(accrual_start, cf.end_date, day_count)
        coupon = notional * (rate + spread) * tau
        df     = disc_curve.get_disc(cf.payment_date)
        pv    += coupon * df

    return pv


def price_irs(
    trade: Dict,
    float_cfs: List[FloatCashflow],
    fixed_cfs: List[FixedCashflow],
    disc_curve: IRCurve,
    fwd_curve: IRCurve,
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Price an Interest Rate Swap and return its NPV.

    The value_date used for discounting is taken from trade["OverrideValueDate"]
    if set, otherwise trade["ValueDate"].

    Fixings
    -------
    Pass the relevant fixings dict (e.g. fixings_6m from load_fixings()).
    For any float period whose reset_date <= value_date, the historical
    fixing is used instead of the forward curve.  If fixings is None or
    a reset_date is missing, the forward curve is used as fallback.

    Pay/Receive convention
    ----------------------
    "Rec"  : receive fixed, pay floating  ->  NPV = PV_fixed - PV_float
    "Pay"  : pay fixed, receive floating  ->  NPV = PV_float - PV_fixed

    Parameters
    ----------
    trade      : dict                      - trade details (irs_orig / irs_bumped style)
    float_cfs  : list[FloatCashflow]
    fixed_cfs  : list[FixedCashflow]
    disc_curve : IRCurve                   - discounting curve
    fwd_curve  : IRCurve                   - forward / projection curve
    fixings    : dict[date, float] | None  - historical fixings (6M SAIBOR, in %)

    Returns
    -------
    dict with keys:
        "pv_fixed"  : float  - PV of fixed leg  (always positive sign)
        "pv_float"  : float  - PV of float leg  (always positive sign)
        "npv"       : float  - NPV from the trade's perspective
    """
    value_date = trade.get("OverrideValueDate") or trade["ValueDate"]
    pay_rec    = trade["PayReceive"].strip().upper()
    fixings    = fixings or {}

    pv_fixed = _price_fixed_leg(trade, fixed_cfs, disc_curve, value_date)
    pv_float = _price_float_leg(trade, float_cfs, disc_curve, fwd_curve, fixings, value_date)

    if pay_rec == "REC":
        npv = pv_fixed - pv_float
    elif pay_rec == "PAY":
        npv = pv_float - pv_fixed
    else:
        raise ValueError(f"PayReceive must be 'Rec' or 'Pay', got '{trade['PayReceive']}'.")

    return {
        "pv_fixed": pv_fixed,
        "pv_float": pv_float,
        "npv":      npv,
    }
