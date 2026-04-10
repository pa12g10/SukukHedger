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
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Price an Interest Rate Swap and return its NPV.

    The value_date is taken from trade["OverrideValueDate"] if set,
    otherwise trade["ValueDate"].

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
    fixings    : dict[date, float] | None  - historical fixings (6M SAIBOR, in %)

    Returns
    -------
    dict  {"pv_fixed": float, "pv_float": float, "npv": float}
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


def get_all_irs_results(
    trade: Dict,
    float_cfs: List[FloatCashflow],
    fixed_cfs: List[FixedCashflow],
    curves: Dict[str, IRCurve],
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Run all IRS pricing scenarios and return NPV plus Greek deltas.

    Curve keys are derived from trade["DiscCurveName"] and
    trade["FwdCurveName"] by replacing the trailing "_Orig" suffix with
    "_Bumped".  Both the base (Orig) and shocked (Bumped) curves must
    be present in *curves*.

    Scenarios
    ---------
    base NPV          : disc_orig  + fwd_orig   (the clean mark-to-market)
    disc_curve_delta  : disc_bumped + fwd_orig  minus base NPV
                        -> sensitivity to a parallel shift of the disc curve
    fwd_curve_delta   : disc_orig  + fwd_bumped minus base NPV
                        -> sensitivity to a parallel shift of the fwd curve
    total_delta       : disc_curve_delta + fwd_curve_delta

    Parameters
    ----------
    trade      : dict                        - trade details (must contain
                                               DiscCurveName and FwdCurveName
                                               ending in '_Orig')
    float_cfs  : list[FloatCashflow]
    fixed_cfs  : list[FixedCashflow]
    curves     : dict[str, IRCurve]          - full curves dict from load_curves()
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
    disc_orig_key   = trade["DiscCurveName"]
    fwd_orig_key    = trade["FwdCurveName"]

    if not disc_orig_key.endswith("_Orig"):
        raise ValueError(
            f"DiscCurveName '{disc_orig_key}' must end with '_Orig' to "
            f"derive the bumped curve key."
        )
    if not fwd_orig_key.endswith("_Orig"):
        raise ValueError(
            f"FwdCurveName '{fwd_orig_key}' must end with '_Orig' to "
            f"derive the bumped curve key."
        )

    disc_bumped_key = disc_orig_key[:-5] + "_Bumped"   # replace trailing _Orig
    fwd_bumped_key  = fwd_orig_key[:-5]  + "_Bumped"

    disc_orig   = curves[disc_orig_key]
    fwd_orig    = curves[fwd_orig_key]
    disc_bumped = curves[disc_bumped_key]
    fwd_bumped  = curves[fwd_bumped_key]

    # --- Base NPV (orig disc + orig fwd) ---
    base = price_irs(trade, float_cfs, fixed_cfs, disc_orig, fwd_orig, fixings)

    # --- Disc curve delta: bump disc, keep fwd flat ---
    npv_disc_bumped  = price_irs(trade, float_cfs, fixed_cfs, disc_bumped, fwd_orig, fixings)["npv"]
    disc_curve_delta = npv_disc_bumped - base["npv"]

    # --- Fwd curve delta: bump fwd, keep disc flat ---
    npv_fwd_bumped  = price_irs(trade, float_cfs, fixed_cfs, disc_orig, fwd_bumped, fixings)["npv"]
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
