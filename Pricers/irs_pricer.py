# irs_pricer.py
# Written by Peter Allen - R&C
# 10 April 2026
# IRS NPV pricer for Hedge Effectiveness Calculation

from __future__ import annotations

from datetime import date
from typing import Dict, List

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

    Each period:  CF = Notional * FixedRate * year_fraction(start, end)
    PV           = CF * DF(payment_date)
    Periods with payment_date <= value_date are excluded (already settled).
    """
    notional   = trade["Notional"]
    fixed_rate = trade["FixedRate"]
    day_count  = trade["DayCount"]
    pv = 0.0

    for cf in fixed_cfs:
        if cf.payment_date <= value_date:
            continue
        tau = year_fraction(cf.start_date, cf.end_date, day_count)
        coupon = notional * fixed_rate * tau
        df = disc_curve.get_disc(cf.payment_date)
        pv += coupon * df

    return pv


def _price_float_leg(
    trade: Dict,
    float_cfs: List[FloatCashflow],
    disc_curve: IRCurve,
    fwd_curve: IRCurve,
    value_date: date,
) -> float:
    """
    PV of the floating leg.

    Each period:  fwd_rate = get_forward(start_date, end_date)  [from fwd_curve]
                  CF       = Notional * (fwd_rate + Spread) * tau
                  PV       = CF * DF(payment_date)             [from disc_curve]

    Spread defaults to 0 if not present in trade dict.
    Periods with payment_date <= value_date are excluded.
    """
    notional  = trade["Notional"]
    spread    = trade.get("Spread", 0.0)
    day_count = trade["DayCount"]
    pv = 0.0

    for cf in float_cfs:
        if cf.payment_date <= value_date:
            continue
        fwd_rate = fwd_curve.get_forward(cf.start_date, cf.end_date)
        tau      = year_fraction(cf.start_date, cf.end_date, day_count)
        coupon   = notional * (fwd_rate + spread) * tau
        df       = disc_curve.get_disc(cf.payment_date)
        pv += coupon * df

    return pv


def price_irs(
    trade: Dict,
    float_cfs: List[FloatCashflow],
    fixed_cfs: List[FixedCashflow],
    disc_curve: IRCurve,
    fwd_curve: IRCurve,
) -> Dict[str, float]:
    """
    Price an Interest Rate Swap and return its NPV.

    The value_date used for discounting is taken from trade["OverrideValueDate"]
    if set, otherwise trade["ValueDate"].

    Pay/Receive convention
    ----------------------
    "Rec"  : receive fixed, pay floating  ->  NPV = PV_fixed - PV_float
    "Pay"  : pay fixed, receive floating  ->  NPV = PV_float - PV_fixed

    Parameters
    ----------
    trade      : dict   - trade details (irs_orig / irs_bumped style)
    float_cfs  : list[FloatCashflow]
    fixed_cfs  : list[FixedCashflow]
    disc_curve : IRCurve  - discounting curve
    fwd_curve  : IRCurve  - forward / projection curve

    Returns
    -------
    dict with keys:
        "pv_fixed"  : float  - PV of fixed leg  (always positive sign)
        "pv_float"  : float  - PV of float leg  (always positive sign)
        "npv"       : float  - NPV from the trade's perspective
    """
    value_date = trade.get("OverrideValueDate") or trade["ValueDate"]
    pay_rec    = trade["PayReceive"].strip().upper()

    pv_fixed = _price_fixed_leg(trade, fixed_cfs, disc_curve, value_date)
    pv_float = _price_float_leg(trade, float_cfs, disc_curve, fwd_curve, value_date)

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
