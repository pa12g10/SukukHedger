# main.py
# Written by Peter Allen - R&C
# 10 April 2026

from Utilities.curve_parser import load_curves


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


if __name__ == "__main__":
    main()
