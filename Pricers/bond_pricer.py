# bond_pricer.py
# Written by Peter Allen - R&C
# 10 April 2026
# Floating-rate bond (Sukuk) NPV pricer for Hedge Effectiveness Calculation

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from Model.ir_curve import IRCurve
from Utilities.cf_parser import FloatCashflow
from Utilities.utils import year_fraction


def _build_curve_keys(trade: Dict) -> tuple:
    """
    Derive the four curve keys needed for base + bumped pricing.

    The full curve key is assembled as:
        {valuation_date}_{CurveName}_Orig   (base)
        {valuation_date}_{CurveName}_Bumped (shocked)

    where valuation_date is formatted as YYYY-MM-DD and CurveName is
    the short name stored in trade["DiscCurveName"] / trade["FwdCurveName"]
    (e.g. "Disc_3M", "Fwd_6M").

    Returns
    -------
    (disc_orig_key, disc_bumped_key, fwd_orig_key, fwd_bumped_key)
    """
    value_date = trade.get("OverrideValueDate") or trade["ValueDate"]
    date_pfx   = value_date.strftime("%Y-%m-%d")

    disc_orig_key   = f"{date_pfx}_{trade['DiscCurveName']}_Orig"
    disc_bumped_key = f"{date_pfx}_{trade['DiscCurveName']}_Bumped"
    fwd_orig_key    = f"{date_pfx}_{trade['FwdCurveName']}_Orig"
    fwd_bumped_key  = f"{date_pfx}_{trade['FwdCurveName']}_Bumped"

    return disc_orig_key, disc_bumped_key, fwd_orig_key, fwd_bumped_key


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
    _price_coupon_leg, not here.  This function returns only the rate.
    """
    if cf.reset_date <= value_date:
        if cf.reset_date in fixings:
            return fixings[cf.reset_date] / 100.0
        return fwd_curve.get_forward(cf.start_date, cf.end_date)
    return fwd_curve.get_forward(cf.start_date, cf.end_date)


def _price_coupon_leg(
    trade: Dict,
    cfs: List[FloatCashflow],
    disc_curve: IRCurve,
    fwd_curve: IRCurve,
    fixings: Dict[date, float],
    value_date: date,
) -> float:
    """
    PV of all future floating coupons, computed on a single FaceValue bond.

    Each period:
      - Skip entirely if end_date    <= value_date  (period fully elapsed).
      - Skip entirely if payment_date <= value_date (already settled).
      - If start_date < value_date, clamp accrual start to value_date so we
        only accrue the remaining stub of the current period.
      - rate   = historical fixing (if reset_date <= value_date) else forward rate
      - tau    = year_fraction(accrual_start, end_date)
      - CF     = FaceValue * (rate + Spread) * tau
      - PV     = CF * DF(payment_date)

    Spread is mandatory on the bond and taken from trade["Spread"].
    """
    face_value = trade["FaceValue"]
    spread     = trade["Spread"]
    day_count  = trade["DayCount"]
    pv = 0.0

    for cf in cfs:
        if cf.end_date <= value_date:
            continue
        if cf.payment_date <= value_date:
            continue

        accrual_start = max(cf.start_date, value_date)
        rate   = _get_float_rate(cf, fwd_curve, fixings, value_date)
        tau    = year_fraction(accrual_start, cf.end_date, day_count)
        coupon = face_value * (rate + spread) * tau
        df     = disc_curve.get_disc(cf.payment_date)
        pv    += coupon * df

    return pv


def _price_principal(
    trade: Dict,
    disc_curve: IRCurve,
    value_date: date,
) -> float:
    """
    PV of the face value repayment at maturity.

    Returns 0 if maturity_date <= value_date (already repaid).
    """
    maturity_date = trade["MaturityDate"]
    if maturity_date <= value_date:
        return 0.0
    face_value = trade["FaceValue"]
    df         = disc_curve.get_disc(maturity_date)
    return face_value * df


def price_bond(
    trade: Dict,
    cfs: List[FloatCashflow],
    disc_curve: IRCurve,
    fwd_curve: IRCurve,
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Price a floating-rate bond (Sukuk) and return its dirty price and NPV.

    Pricing steps
    -------------
    1. bond_pv      = pv_coupons + pv_principal
                      (both computed on a single FaceValue bond)
    2. dirty_price  = bond_pv / FaceValue
                      (price per unit of face, e.g. 0.9823 = 98.23 per 100 face)
    3. npv          = dirty_price * Notional
                      (scaled to the full position)

    The value_date is taken from trade["OverrideValueDate"] if set,
    otherwise trade["ValueDate"].

    Fixings
    -------
    Pass the relevant fixings dict (e.g. fixings_6m from load_fixings()).
    For any coupon period whose reset_date <= value_date the historical
    fixing is used.  If fixings is None or a date is missing, the forward
    curve is used as fallback.

    Pay/Receive convention
    ----------------------
    "Rec"  : we receive the bond cashflows  ->  NPV = +dirty_price * Notional
    "Pay"  : we pay the bond cashflows      ->  NPV = -dirty_price * Notional

    Parameters
    ----------
    trade      : dict                        - trade details (sukuk style)
    cfs        : list[FloatCashflow]         - coupon schedule
    disc_curve : IRCurve                     - discounting curve
    fwd_curve  : IRCurve                     - forward / projection curve
    fixings    : dict[date, float] | None    - historical fixings (6M SAIBOR, in %)

    Returns
    -------
    dict with keys:
        "pv_coupons"   : float  - PV of future coupons  (per FaceValue bond)
        "pv_principal" : float  - PV of principal repayment  (per FaceValue bond)
        "dirty_price"  : float  - bond_pv / FaceValue
        "npv"          : float  - dirty_price * Notional  (+/- by PayReceive)
    """
    value_date = trade.get("OverrideValueDate") or trade["ValueDate"]
    pay_rec    = trade["PayReceive"].strip().upper()
    fixings    = fixings or {}

    pv_coupons   = _price_coupon_leg(trade, cfs, disc_curve, fwd_curve, fixings, value_date)
    pv_principal = _price_principal(trade, disc_curve, value_date)
    bond_pv      = pv_coupons + pv_principal
    dirty_price  = bond_pv / trade["FaceValue"]

    if pay_rec == "REC":
        npv = dirty_price * trade["Notional"]
    elif pay_rec == "PAY":
        npv = -dirty_price * trade["Notional"]
    else:
        raise ValueError(f"PayReceive must be 'Rec' or 'Pay', got '{trade['PayReceive']}'.")

    return {
        "pv_coupons":   pv_coupons,
        "pv_principal": pv_principal,
        "dirty_price":  dirty_price,
        "npv":          npv,
    }


def get_all_bond_results(
    trade: Dict,
    cfs: List[FloatCashflow],
    curves: Dict[str, IRCurve],
    fixings: Optional[Dict[date, float]] = None,
) -> Dict[str, float]:
    """
    Run all bond pricing scenarios and return NPV plus Greek deltas.

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
    trade      : dict                        - trade details (sukuk style)
    cfs        : list[FloatCashflow]         - coupon schedule
    curves     : dict[str, IRCurve]          - full curves dict from load_curves()
    fixings    : dict[date, float] | None    - historical fixings (6M SAIBOR, in %)

    Returns
    -------
    dict with keys:
        "npv"              : float  - base NPV  (= dirty_price * Notional)
        "pv_coupons"       : float  - PV of coupons per FaceValue bond (base)
        "pv_principal"     : float  - PV of principal per FaceValue bond (base)
        "dirty_price"      : float  - bond_pv / FaceValue (base)
        "disc_curve_delta" : float  - NPV change from bumped disc curve
        "fwd_curve_delta"  : float  - NPV change from bumped fwd curve
        "total_delta"      : float  - disc_curve_delta + fwd_curve_delta
    """
    disc_orig_key, disc_bumped_key, fwd_orig_key, fwd_bumped_key = _build_curve_keys(trade)

    disc_orig   = curves[disc_orig_key]
    fwd_orig    = curves[fwd_orig_key]
    disc_bumped = curves[disc_bumped_key]
    fwd_bumped  = curves[fwd_bumped_key]

    # --- Base NPV ---
    base = price_bond(trade, cfs, disc_orig, fwd_orig, fixings)

    # --- Disc curve delta: bump disc, keep fwd flat ---
    npv_disc_bumped  = price_bond(trade, cfs, disc_bumped, fwd_orig, fixings)["npv"]
    disc_curve_delta = npv_disc_bumped - base["npv"]

    # --- Fwd curve delta: bump fwd, keep disc flat ---
    npv_fwd_bumped  = price_bond(trade, cfs, disc_orig, fwd_bumped, fixings)["npv"]
    fwd_curve_delta = npv_fwd_bumped - base["npv"]

    total_delta = disc_curve_delta + fwd_curve_delta

    return {
        "npv":              base["npv"],
        "pv_coupons":       base["pv_coupons"],
        "pv_principal":     base["pv_principal"],
        "dirty_price":      base["dirty_price"],
        "disc_curve_delta": disc_curve_delta,
        "fwd_curve_delta":  fwd_curve_delta,
        "total_delta":      total_delta,
    }
