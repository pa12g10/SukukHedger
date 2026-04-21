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
import QuantLib as QL


def _build_curve_keys(trade: Dict, value_date: date) -> tuple:
    """
    Derive the four curve keys needed for base + bumped pricing.

    The full curve key is assembled as:
        {valuation_date}_{CurveName}_Orig   (base)
        {valuation_date}_{CurveName}_Bumped (shocked)

    where valuation_date is formatted as YYYY-MM-DD and CurveName is
    the short name stored in trade["DiscCurveName"] / trade["FwdCurveName"]
    (e.g. "Disc_3M", "Fwd_6M").

    OverrideValueDate takes precedence over value_date if set.

    Returns
    -------
    (disc_orig_key, disc_bumped_key, fwd_orig_key, fwd_bumped_key)
    """
    effective_date = trade.get("OverrideValueDate") or value_date
    date_pfx       = effective_date.strftime("%Y-%m-%d")

    disc_orig_key   = f"{date_pfx}_{trade['DiscCurveName']}_Orig"
    disc_bumped_key = f"{date_pfx}_{trade['DiscCurveName']}_Bumped"
    fwd_orig_key    = f"{date_pfx}_{trade['FwdCurveName']}_Orig"
    fwd_bumped_key  = f"{date_pfx}_{trade['FwdCurveName']}_Bumped"

    return disc_orig_key, disc_bumped_key, fwd_orig_key, fwd_bumped_key


def _price_fixed_leg(
    trade: Dict,
    fixed_cfs: List[FixedCashflow],
    disc_curve: IRCurve,
    value_date: date,
) -> float:
    """
    PV of the fixed leg.

    Each period:
      - Skip entirely if end_date    <= value_date  (period fully elapsed).
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
        if cf.end_date <= value_date:
            continue
        if cf.payment_date <= value_date:
            continue

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

    Note: year-fraction / accrual-start clamping is handled in
    _price_float_leg, not here.  This function returns only the rate.
    """
    if cf.reset_date <= value_date:
        if cf.reset_date in fixings:
            return fixings[cf.reset_date] / 100.0
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
        if cf.end_date <= value_date:
            continue
        if cf.payment_date <= value_date:
            continue

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
    value_date: date,
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Price an Interest Rate Swap and return its NPV.

    value_date is the valuation date passed explicitly by the caller.
    If trade["OverrideValueDate"] is set it takes precedence.

    Fixings
    -------
    Pass the relevant fixings dict (e.g. fixings_6m from load_fixings()).
    For any float period whose reset_date <= value_date the historical
    fixing is used.  If fixings is None or a date is missing, the forward
    curve is used as fallback.

    Pay/Receive convention
    ----------------------
    "Rec"  : receive fixed, pay floating  ->  NPV = PV_fixed - PV_float
    "Pay"  : pay fixed, receive floating  ->  NPV = PV_float - PV_fixed

    Parameters
    ----------
    trade      : dict                      - trade details
    float_cfs  : list[FloatCashflow]
    fixed_cfs  : list[FixedCashflow]
    disc_curve : IRCurve                   - discounting curve
    fwd_curve  : IRCurve                   - forward / projection curve
    value_date : date                      - valuation date
    fixings    : dict[date, float] | None  - historical fixings (6M SAIBOR, in %)

    Returns
    -------
    dict  {"pv_fixed": float, "pv_float": float, "npv": float}
    """
    effective_date = trade.get("OverrideValueDate") or value_date
    pay_rec        = trade["PayReceive"].strip().upper()
    fixings        = fixings or {}

    pv_fixed = _price_fixed_leg(trade, fixed_cfs, disc_curve, effective_date)
    pv_float = _price_float_leg(trade, float_cfs, disc_curve, fwd_curve, fixings, effective_date)

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


def get_all_irs_results(
    trade: Dict,
    float_cfs: List[FloatCashflow],
    fixed_cfs: List[FixedCashflow],
    curves: Dict[str, IRCurve],
    value_date: date,
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Run all IRS pricing scenarios and return NPV plus Greek deltas.

    Full curve keys are built by concatenating:
        {valuation_date}_{trade["DiscCurveName"]}_Orig   (e.g. "2025-12-31_Disc_3M_Orig")
        {valuation_date}_{trade["DiscCurveName"]}_Bumped
        {valuation_date}_{trade["FwdCurveName"]}_Orig
        {valuation_date}_{trade["FwdCurveName"]}_Bumped

    where trade["DiscCurveName"] and trade["FwdCurveName"] are short names
    such as "Disc_3M" and "Fwd_6M".

    Scenarios
    ---------
    base NPV          : disc_orig   + fwd_orig   (clean mark-to-market)
    disc_curve_delta  : disc_bumped + fwd_orig   minus base NPV
    fwd_curve_delta   : disc_orig   + fwd_bumped minus base NPV
    total_delta       : disc_curve_delta + fwd_curve_delta

    Parameters
    ----------
    trade      : dict                        - trade details
    float_cfs  : list[FloatCashflow]
    fixed_cfs  : list[FixedCashflow]
    curves     : dict[str, IRCurve]          - full curves dict from load_curves()
    value_date : date                        - valuation date
    fixings    : dict[date, float] | None    - historical fixings (6M SAIBOR, in %)

    Returns
    -------
    dict with keys:
        "npv"              : float  - base NPV (orig disc + orig fwd)
        "pv_fixed"         : float  - PV of fixed leg (base)
        "pv_float"         : float  - PV of float leg (base)
        "disc_curve_delta" : float  - NPV change from bumped disc curve
        "fwd_curve_delta"  : float  - NPV change from bumped fwd curve
        "total_delta"      : float  - disc_curve_delta + fwd_curve_delta
    """
    disc_orig_key, disc_bumped_key, fwd_orig_key, fwd_bumped_key = _build_curve_keys(trade, value_date)

    disc_orig   = curves[disc_orig_key]
    fwd_orig    = curves[fwd_orig_key]
    disc_bumped = curves[disc_bumped_key]
    fwd_bumped  = curves[fwd_bumped_key]

    # --- Base NPV ---
    base = price_irs(trade, float_cfs, fixed_cfs, disc_orig, fwd_orig, value_date, fixings)

    # --- Disc curve delta: bump disc, keep fwd flat ---
    npv_disc_bumped  = price_irs(trade, float_cfs, fixed_cfs, disc_bumped, fwd_orig, value_date, fixings)["npv"]
    disc_curve_delta = npv_disc_bumped - base["npv"]

    # --- Fwd curve delta: bump fwd, keep disc flat ---
    npv_fwd_bumped  = price_irs(trade, float_cfs, fixed_cfs, disc_orig, fwd_bumped, value_date, fixings)["npv"]
    fwd_curve_delta = npv_fwd_bumped - base["npv"]

    total_delta = disc_curve_delta + fwd_curve_delta

    return {
        "npv":              base["npv"],
        "pv_fixed":         base["pv_fixed"],
        "pv_float":         base["pv_float"],
        "disc_curve_delta": disc_curve_delta,
        "fwd_curve_delta":  fwd_curve_delta,
        "total_delta":      total_delta,
    }
