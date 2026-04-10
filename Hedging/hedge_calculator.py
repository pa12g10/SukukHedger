# hedge_calculator.py
# Written by Peter Allen - R&C
# 10 April 2026
# Hedge effectiveness calculator — delta hedge ratio (designation date)
# and dollar-offset effectiveness (assessment period).

from __future__ import annotations

from datetime import date
from typing import Dict


# ------------------------------------------------------------------ #
# Types                                                               #
# ------------------------------------------------------------------ #

# IRS result dict keys:   npv, pv_fixed, pv_float,
#                         disc_curve_delta, fwd_curve_delta, total_delta
# Bond result dict keys:  npv, pv_coupons, pv_principal, dirty_price,
#                         disc_curve_delta, fwd_curve_delta, total_delta

IRSResult  = Dict[str, float]
BondResult = Dict[str, float]


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _combine_irs(h1: IRSResult, h2: IRSResult) -> Dict[str, float]:
    """
    Aggregate H1 and H2 IRS results into a single combined hedge position.
    All numeric fields are summed.
    """
    return {
        "npv":              h1["npv"]              + h2["npv"],
        "pv_fixed":         h1["pv_fixed"]         + h2["pv_fixed"],
        "pv_float":         h1["pv_float"]         + h2["pv_float"],
        "disc_curve_delta": h1["disc_curve_delta"] + h2["disc_curve_delta"],
        "fwd_curve_delta":  h1["fwd_curve_delta"]  + h2["fwd_curve_delta"],
        "total_delta":      h1["total_delta"]      + h2["total_delta"],
    }


def _pct(numerator: float, denominator: float) -> float:
    """Return numerator / denominator as a percentage. Returns 0 if denominator is zero."""
    return (numerator / denominator * 100) if denominator else 0.0


def _offset_ratio(hedge_delta: float, item_delta: float) -> float:
    """
    Dollar-offset ratio: how much of the hedged item's delta/NPV change
    is offset by the hedging instrument.

    A perfect hedge gives -100% (equal and opposite).
    Positive means the hedge moves in the same direction as the item (wrong way).
    """
    return _pct(-hedge_delta, item_delta)


# ------------------------------------------------------------------ #
# Main public function                                                 #
# ------------------------------------------------------------------ #

def hedge_effectiveness(
    h1_start:     IRSResult,
    h2_start:     IRSResult,
    sukuk_start:  BondResult,
    h1_end:       IRSResult,
    h2_end:       IRSResult,
    sukuk_end:    BondResult,
    start_date:   date,
    end_date:     date,
) -> Dict[str, object]:
    """
    Compute hedge designation metrics and period effectiveness.

    Designation metrics (start_date)
    ---------------------------------
    Hedge ratio (delta-based):
        hr_total = IRS_combined_total_delta / sukuk_total_delta
        hr_disc  = IRS_combined_disc_delta  / sukuk_disc_delta
        hr_fwd   = IRS_combined_fwd_delta   / sukuk_fwd_delta

    A ratio of -1.0 means perfectly offsetting (equal and opposite).
    A ratio of 0.0 means no offset.

    Period effectiveness (start_date → end_date)
    ---------------------------------------------
    Dollar-offset method:
        ΔNPV_sukuk     = sukuk_end[npv]       - sukuk_start[npv]
        ΔNPV_irs       = irs_combined_end[npv] - irs_combined_start[npv]
        ΔNPV_net       = ΔNPV_sukuk + ΔNPV_irs
        offset_ratio   = -ΔNPV_irs / ΔNPV_sukuk  (in %)

    Delta change over period:
        Δtotal_delta_sukuk = sukuk_end[total_delta] - sukuk_start[total_delta]
        Δtotal_delta_irs   = irs_combined_end[total_delta] - irs_combined_start[total_delta]

    Parameters
    ----------
    h1_start / h2_start / sukuk_start  : results at the designation (start) date
    h1_end   / h2_end   / sukuk_end    : results at the assessment (end) date
    start_date                          : hedge designation / period start date
    end_date                            : period end date

    Returns
    -------
    dict — see keys below, all floats unless noted.

    Designation keys (prefix 'des_'):
        des_sukuk_npv            sukuk NPV at start
        des_irs_npv              combined IRS NPV at start
        des_net_npv              net portfolio NPV at start
        des_sukuk_disc_delta     sukuk disc_curve_delta at start
        des_sukuk_fwd_delta      sukuk fwd_curve_delta at start
        des_sukuk_total_delta    sukuk total_delta at start
        des_irs_disc_delta       combined IRS disc_curve_delta at start
        des_irs_fwd_delta        combined IRS fwd_curve_delta at start
        des_irs_total_delta      combined IRS total_delta at start
        des_net_disc_delta       net disc_curve_delta at start
        des_net_fwd_delta        net fwd_curve_delta at start
        des_net_total_delta      net total_delta at start
        des_hr_disc              hedge ratio — disc curve delta
        des_hr_fwd               hedge ratio — fwd curve delta
        des_hr_total             hedge ratio — total delta

    Period effectiveness keys (prefix 'eff_'):
        eff_dnpv_sukuk           ΔNPV of sukuk over period
        eff_dnpv_irs             ΔNPV of combined IRS over period
        eff_dnpv_net             net ΔNPV over period
        eff_offset_ratio_pct     dollar-offset ratio (%); -100 = perfect hedge
        eff_sukuk_disc_delta_end sukuk disc_delta at end date
        eff_sukuk_fwd_delta_end  sukuk fwd_delta at end date
        eff_sukuk_total_delta_end sukuk total_delta at end date
        eff_irs_disc_delta_end   combined IRS disc_delta at end date
        eff_irs_fwd_delta_end    combined IRS fwd_delta at end date
        eff_irs_total_delta_end  combined IRS total_delta at end date
        eff_net_disc_delta_end   net disc_delta at end date
        eff_net_fwd_delta_end    net fwd_delta at end date
        eff_net_total_delta_end  net total_delta at end date
        eff_delta_stability_pct  how stable the hedge ratio was: end hr_total vs start hr_total
    """
    irs_start = _combine_irs(h1_start, h2_start)
    irs_end   = _combine_irs(h1_end,   h2_end)

    # ── Designation metrics ─────────────────────────────────────────
    des_net_disc  = sukuk_start["disc_curve_delta"] + irs_start["disc_curve_delta"]
    des_net_fwd   = sukuk_start["fwd_curve_delta"]  + irs_start["fwd_curve_delta"]
    des_net_total = sukuk_start["total_delta"]       + irs_start["total_delta"]

    hr_disc  = _offset_ratio(irs_start["disc_curve_delta"], sukuk_start["disc_curve_delta"])
    hr_fwd   = _offset_ratio(irs_start["fwd_curve_delta"],  sukuk_start["fwd_curve_delta"])
    hr_total = _offset_ratio(irs_start["total_delta"],      sukuk_start["total_delta"])

    # ── Period effectiveness ────────────────────────────────────────
    dnpv_sukuk = sukuk_end["npv"] - sukuk_start["npv"]
    dnpv_irs   = irs_end["npv"]   - irs_start["npv"]
    dnpv_net   = dnpv_sukuk + dnpv_irs
    offset_pct = _offset_ratio(dnpv_irs, dnpv_sukuk)

    # End-date delta snapshot
    end_net_disc  = sukuk_end["disc_curve_delta"] + irs_end["disc_curve_delta"]
    end_net_fwd   = sukuk_end["fwd_curve_delta"]  + irs_end["fwd_curve_delta"]
    end_net_total = sukuk_end["total_delta"]       + irs_end["total_delta"]

    # Hedge ratio stability: end hr_total vs start hr_total
    hr_total_end      = _offset_ratio(irs_end["total_delta"], sukuk_end["total_delta"])
    delta_stability   = hr_total_end - hr_total   # 0 = perfectly stable

    return {
        # ── Designation ────────────────────────────────────────────
        "start_date":                start_date,
        "end_date":                  end_date,

        "des_sukuk_npv":             sukuk_start["npv"],
        "des_irs_npv":               irs_start["npv"],
        "des_net_npv":               sukuk_start["npv"] + irs_start["npv"],

        "des_sukuk_disc_delta":      sukuk_start["disc_curve_delta"],
        "des_sukuk_fwd_delta":       sukuk_start["fwd_curve_delta"],
        "des_sukuk_total_delta":     sukuk_start["total_delta"],
        "des_irs_disc_delta":        irs_start["disc_curve_delta"],
        "des_irs_fwd_delta":         irs_start["fwd_curve_delta"],
        "des_irs_total_delta":       irs_start["total_delta"],
        "des_net_disc_delta":        des_net_disc,
        "des_net_fwd_delta":         des_net_fwd,
        "des_net_total_delta":       des_net_total,

        "des_hr_disc_pct":           hr_disc,
        "des_hr_fwd_pct":            hr_fwd,
        "des_hr_total_pct":          hr_total,

        # ── Period effectiveness ────────────────────────────────────
        "eff_dnpv_sukuk":            dnpv_sukuk,
        "eff_dnpv_irs":              dnpv_irs,
        "eff_dnpv_net":              dnpv_net,
        "eff_offset_ratio_pct":      offset_pct,

        "eff_sukuk_disc_delta_end":  sukuk_end["disc_curve_delta"],
        "eff_sukuk_fwd_delta_end":   sukuk_end["fwd_curve_delta"],
        "eff_sukuk_total_delta_end": sukuk_end["total_delta"],
        "eff_irs_disc_delta_end":    irs_end["disc_curve_delta"],
        "eff_irs_fwd_delta_end":     irs_end["fwd_curve_delta"],
        "eff_irs_total_delta_end":   irs_end["total_delta"],
        "eff_net_disc_delta_end":    end_net_disc,
        "eff_net_fwd_delta_end":     end_net_fwd,
        "eff_net_total_delta_end":   end_net_total,

        "eff_hr_total_end_pct":      hr_total_end,
        "eff_delta_stability_pct":   delta_stability,
    }


def print_hedge_report(results: Dict[str, object]) -> None:
    """
    Print a formatted hedge effectiveness report to stdout.

    Parameters
    ----------
    results : dict returned by hedge_effectiveness()
    """
    r = results
    sep = "=" * 65
    thin = "-" * 65

    print(sep)
    print(f"  HEDGE EFFECTIVENESS REPORT")
    print(f"  Designation : {r['start_date']}    Assessment end : {r['end_date']}")
    print(sep)

    print()
    print("  DESIGNATION DATE SNAPSHOT")
    print(thin)
    print(f"  {'':30s}  {'Sukuk':>12}  {'IRS (H1+H2)':>12}  {'Net':>12}")
    print(thin)
    print(f"  {'NPV':30s}  {r['des_sukuk_npv']:>12,.0f}  {r['des_irs_npv']:>12,.0f}  {r['des_net_npv']:>12,.0f}")
    print(f"  {'disc_curve_delta (1bp)':30s}  {r['des_sukuk_disc_delta']:>12,.0f}  {r['des_irs_disc_delta']:>12,.0f}  {r['des_net_disc_delta']:>12,.0f}")
    print(f"  {'fwd_curve_delta  (1bp)':30s}  {r['des_sukuk_fwd_delta']:>12,.0f}  {r['des_irs_fwd_delta']:>12,.0f}  {r['des_net_fwd_delta']:>12,.0f}")
    print(f"  {'total_delta      (1bp)':30s}  {r['des_sukuk_total_delta']:>12,.0f}  {r['des_irs_total_delta']:>12,.0f}  {r['des_net_total_delta']:>12,.0f}")
    print()
    print(f"  DELTA HEDGE RATIOS (designation)")
    print(thin)
    print(f"  {'disc_curve hedge ratio':30s}  {r['des_hr_disc_pct']:>+11.1f}%  (ideal: -100%)")
    print(f"  {'fwd_curve  hedge ratio':30s}  {r['des_hr_fwd_pct']:>+11.1f}%  (ideal: -100%)")
    print(f"  {'total      hedge ratio':30s}  {r['des_hr_total_pct']:>+11.1f}%  (ideal: -100%)")

    print()
    print("  PERIOD EFFECTIVENESS  (ΔNPV dollar-offset)")
    print(thin)
    print(f"  {'ΔNPV Sukuk':30s}  {r['eff_dnpv_sukuk']:>12,.0f}")
    print(f"  {'ΔNPV IRS combined':30s}  {r['eff_dnpv_irs']:>12,.0f}")
    print(f"  {'ΔNPV Net':30s}  {r['eff_dnpv_net']:>12,.0f}")
    print(f"  {'Offset ratio':30s}  {r['eff_offset_ratio_pct']:>+11.1f}%  (ideal: -100%)")

    print()
    print("  END-DATE DELTA SNAPSHOT")
    print(thin)
    print(f"  {'':30s}  {'Sukuk':>12}  {'IRS (H1+H2)':>12}  {'Net':>12}")
    print(thin)
    print(f"  {'disc_curve_delta (1bp)':30s}  {r['eff_sukuk_disc_delta_end']:>12,.0f}  {r['eff_irs_disc_delta_end']:>12,.0f}  {r['eff_net_disc_delta_end']:>12,.0f}")
    print(f"  {'fwd_curve_delta  (1bp)':30s}  {r['eff_sukuk_fwd_delta_end']:>12,.0f}  {r['eff_irs_fwd_delta_end']:>12,.0f}  {r['eff_net_fwd_delta_end']:>12,.0f}")
    print(f"  {'total_delta      (1bp)':30s}  {r['eff_sukuk_total_delta_end']:>12,.0f}  {r['eff_irs_total_delta_end']:>12,.0f}  {r['eff_net_total_delta_end']:>12,.0f}")
    print()
    print(f"  {'Total hedge ratio (end)':30s}  {r['eff_hr_total_end_pct']:>+11.1f}%")
    print(f"  {'HR drift (end - start)':30s}  {r['eff_delta_stability_pct']:>+11.1f}%  (ideal: 0%)")
    print(sep)
