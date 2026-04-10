# main.py
# Written by Peter Allen - R&C
# 10 April 2026

from datetime import date

from Pricers.bond_pricer import get_all_bond_results
from Pricers.irs_pricer import price_irs, get_all_irs_results
from Utilities.curve_parser import load_curves, load_fixings
from Utilities.cf_parser import load_fixed_cashflows, load_float_cashflows

from Hedging.hedge_calculator import hedge_effectiveness, print_hedge_report

# ------------------------------------------------------------------ #
# IRS Trade Definitions                                               #
# ------------------------------------------------------------------ #

irs_h1 = {
    "Notional":           159_000_000,
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2026, 1, 4),
    "MaturityDate":       date(2036, 1, 4),
    "FwdCurveName":       "Fwd_6M",
    "DiscCurveName":      "Disc_3M",
    "PayReceive":         "Rec",
    "FixedRate":          0.0486,
    "DayCount":           "ACT/360",
}

irs_h2 = {
    "Notional":           159_000_000,
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2026, 1, 4),
    "MaturityDate":       date(2036, 1, 4),
    "FwdCurveName":       "Fwd_6M",
    "DiscCurveName":      "Disc_3M",
    "PayReceive":         "Rec",
    "FixedRate":          0.0486,
    "DayCount":           "ACT/360",
}


# ------------------------------------------------------------------ #
# Sukuk Trade Definition                                              #
# ------------------------------------------------------------------ #

sukuk = {
    "Notional":           250_000_000,
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2024, 5, 27),
    "MaturityDate":       date(2039, 5, 29),
    "FwdCurveName":       "Fwd_6M",
    "DiscCurveName":      "Disc_3M",
    "PayReceive":         "Rec",
    "Spread":             0.001,
    "DayCount":           "30/360",
    "FaceValue":          1000,
}


# ------------------------------------------------------------------ #
# Main                                                                #
# ------------------------------------------------------------------ #

def main():
    value_date_dec = date(2025, 12, 31)
    value_date_mar = date(2026, 3, 31)

    # Load curves
    curves = load_curves(
        filepath="curve_universe.csv",
        day_count_convention="ACT/360",
        interpolation_method="LOG_LINEAR",
    )

    # Load cashflow schedules
    h1_fixed_cfs = load_fixed_cashflows("Instruments/h1_fixed_cfs.csv")
    h1_float_cfs = load_float_cashflows("Instruments/h1_float_cfs.csv")
    h2_fixed_cfs = load_fixed_cashflows("Instruments/h2_fixed_cfs.csv")
    h2_float_cfs = load_float_cashflows("Instruments/h2_float_cfs.csv")
    sukuk_cfs    = load_float_cashflows("Instruments/sukuk_cfs.csv")
    fixings_6m   = load_fixings("6m_fixings.csv")

    h1_results_dec    = get_all_irs_results(irs_h1, h1_float_cfs, h1_fixed_cfs, curves, value_date_dec, fixings_6m)
    h2_results_dec    = get_all_irs_results(irs_h2, h2_float_cfs, h2_fixed_cfs, curves, value_date_dec, fixings_6m)
    sukuk_results_dec = get_all_bond_results(sukuk, sukuk_cfs, curves, value_date_dec, fixings_6m)

    h1_results_mar   = get_all_irs_results(irs_h1, h1_float_cfs, h1_fixed_cfs, curves, value_date_mar, fixings_6m)
    h2_results_mar    = get_all_irs_results(irs_h2, h2_float_cfs, h2_fixed_cfs, curves, value_date_mar, fixings_6m)
    sukuk_results_mar = get_all_bond_results(sukuk, sukuk_cfs, curves, value_date_mar, fixings_6m)

    results = hedge_effectiveness(
        h1_start=h1_results_dec, h2_start=h2_results_dec, sukuk_start=sukuk_results_dec,
        h1_end=h1_results_mar, h2_end=h2_results_mar, sukuk_end=sukuk_results_mar,
        start_date=value_date_dec,
        end_date=value_date_mar,
    )

    print_hedge_report(results)

if __name__ == "__main__":
    main()
