# main.py
# Written by Peter Allen - R&C
# 10 April 2026

from datetime import date
from Utilities.curve_parser import load_curves


# ------------------------------------------------------------------ #
# IRS Trade Definitions                                               #
# ------------------------------------------------------------------ #

irs_orig = {
    "Notional":           100_000_000,          # 100MM
    "ValueDate":          date(2025, 12, 31),
    "OverrideValueDate":  None,                  # not overridden
    "EffectiveDate":      date(2026, 1, 4),
    "MaturityDate":       date(2036, 1, 4),
    "FwdCurveName":       "2025-12-31_Fwd_6M_Orig",
    "DiscCurveName":      "2025-12-31_Disc_3M_Orig",
    "PayReceive":         "Rec",
    "FixedRate":          0.0486,                # 4.86%
}

irs_bumped = {
    "Notional":           100_000_000,
    "ValueDate":          date(2025, 12, 31),
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2026, 1, 4),
    "MaturityDate":       date(2036, 1, 4),
    "FwdCurveName":       "2025-12-31_Fwd_6M_Bumped",
    "DiscCurveName":      "2025-12-31_Disc_3M_Bumped",
    "PayReceive":         "Rec",
    "FixedRate":          0.0486,
}


# ------------------------------------------------------------------ #
# Sukuk Trade Definition                                              #
# ------------------------------------------------------------------ #

sukuk = {
    "Notional":           100_000_000,
    "ValueDate":          date(2025, 12, 31),
    "OverrideValueDate":  None,
    "EffectiveDate":      date(2024, 5, 27),
    "MaturityDate":       date(2039, 5, 27),
    "FwdCurveName":       "2025-12-31_Fwd_6M",
    "DiscCurveName":      "2025-12-31_Disc_3M",
    "PayReceive":         "Rec",
    "Spread":             0.001,                 # 10bps
}


def main():
    # ------------------------------------------------------------------ #
    # Load all curves from the universe file                              #
    # ------------------------------------------------------------------ #
    curve_file = "curve_universe.csv"
    curves = load_curves(
        filepath=curve_file,
        day_count_convention="ACT/365",
        interpolation_method="LOG_LINEAR",
    )

    print(f"Loaded {len(curves)} curves:")
    for key in sorted(curves.keys()):
        c = curves[key]
        print(f"  {key}  |  val_date={c.valuation_date}  |  pillars={len(c.dates)}")

    # ------------------------------------------------------------------ #
    # Print trade summaries                                               #
    # ------------------------------------------------------------------ #
    print("\nIRS (Orig):")
    for k, v in irs_orig.items():
        print(f"  {k}: {v}")

    print("\nIRS (Bumped):")
    for k, v in irs_bumped.items():
        print(f"  {k}: {v}")

    print("\nSukuk:")
    for k, v in sukuk.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
