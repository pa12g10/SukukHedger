# main.py
# Written by Peter Allen - R&C
# 10 April 2026

from datetime import date

from Pricers.bond_pricer import get_all_bond_results
from Pricers.irs_pricer import price_irs, get_all_irs_results
from Utilities.curve_parser import load_curves, load_fixings
from Utilities.cf_parser import load_fixed_cashflows, load_float_cashflows


# ------------------------------------------------------------------ #
# IRS Trade Definitions                                               #
# ------------------------------------------------------------------ #

irs_orig = {
    "Notional":            21_363_643.08 ,
    "ValueDate":          date(2025, 12, 31),
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2026, 1, 4),
    "MaturityDate":       date(2036, 1, 4),
    "FwdCurveName":       "2025-12-31_Fwd_6M_Orig",
    "DiscCurveName":      "2025-12-31_Disc_3M_Orig",
    "PayReceive":         "Rec",
    "FixedRate":          0.0486,
    "DayCount":           "ACT/360",
}

irs_bumped = {
    "Notional":           21_363_643.08,
    "ValueDate":          date(2025, 12, 31),
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2026, 1, 4),
    "MaturityDate":       date(2036, 1, 4),
    "FwdCurveName":       "2025-12-31_Fwd_6M_Bumped",
    "DiscCurveName":      "2025-12-31_Disc_3M_Bumped",
    "PayReceive":         "Rec",
    "FixedRate":          0.0486,
    "DayCount":           "ACT/360",
}


# ------------------------------------------------------------------ #
# Sukuk Trade Definition                                              #
# ------------------------------------------------------------------ #

sukuk = {
    "Notional":            250_000_000,
    "ValueDate":          date(2025, 12, 31),
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2024, 5, 27),
    "MaturityDate":       date(2039, 5, 27),
    "FwdCurveName":       "2025-12-31_Fwd_6M_Orig",
    "DiscCurveName":      "2025-12-31_Disc_3M_Orig",
    "PayReceive":         "Rec",
    "Spread":             0.001,
    "DayCount":           "30/360",
}


# ------------------------------------------------------------------ #
# Main                                                                #
# ------------------------------------------------------------------ #

def main():
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
    fixings_6m = load_fixings("6m_fixings.csv")

    h1_results = get_all_irs_results(irs_orig, h1_float_cfs, h1_fixed_cfs, curves,fixings_6m)
    h2_results = get_all_irs_results(irs_orig, h2_float_cfs, h2_fixed_cfs, curves,fixings_6m)
    sukuk_results = get_all_bond_results(sukuk, sukuk_cfs, curves, fixings_6m)

    print(h1_results)
    print(h2_results)
    print(sukuk_results)

if __name__ == "__main__":
    main()
