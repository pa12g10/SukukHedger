# curve_parser.py
# Written by Peter Allen - R&C
# 10 April 2026
# Reads curve_universe.csv and fixing history CSVs.

from __future__ import annotations

import csv
from datetime import datetime, date
from collections import defaultdict
from typing import Dict

from Model.ir_curve import IRCurve


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_date(date_str: str) -> date:
    """Parse a date string in mm/dd/yyyy format to datetime.date."""
    return datetime.strptime(date_str.strip(), "%m/%d/%Y").date()


def _make_key(curve_date: date, curve: str, tenor: str, curve_type: str) -> str:
    """
    Build a dictionary key for a curve instance.
    Format: 'YYYY-MM-DD_<Curve>_<Tenor>_<CurveType>'
    e.g.  : '2025-12-31_Disc_3M_Orig'
    """
    return f"{curve_date.isoformat()}_{curve}_{tenor}_{curve_type}"


# ------------------------------------------------------------------ #
# Curve loader                                                        #
# ------------------------------------------------------------------ #

def load_curves(
    filepath: str,
    day_count_convention: str = "ACT/360",
    interpolation_method: str = "LOG_LINEAR",
) -> Dict[str, IRCurve]:
    """
    Parse *curve_universe.csv* and return a dictionary of IRCurve instances.

    CSV columns expected
    --------------------
    CurveDate  : mm/dd/yyyy  - valuation date of the curve
    Date       : mm/dd/yyyy  - pillar date
    Curve      : str         - e.g. 'Disc', 'Fwd'
    Tenor      : str         - e.g. '3M', '6M'
    CurveType  : str         - e.g. 'Orig', 'Bumped'
    DF         : float       - discount factor for this pillar

    Parameters
    ----------
    filepath             : str  - path to the CSV file
    day_count_convention : str  - passed to every IRCurve (default 'ACT/365')
    interpolation_method : str  - passed to every IRCurve (default 'LOG_LINEAR')

    Returns
    -------
    dict[str, IRCurve]
        Keys: 'YYYY-MM-DD_<Curve>_<Tenor>_<CurveType>'
        e.g.  '2025-12-31_Disc_3M_Orig'
    """
    buckets: dict = defaultdict(lambda: {"curve_date": None, "dates": [], "dfs": []})

    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            curve_date  = _parse_date(row["CurveDate"])
            pillar_date = _parse_date(row["Date"])
            curve       = row["Curve"].strip()
            tenor       = row["Tenor"].strip()
            curve_type  = row["CurveType"].strip()
            df          = float(row["DF"])

            key = _make_key(curve_date, curve, tenor, curve_type)
            bucket = buckets[key]
            bucket["curve_date"] = curve_date
            bucket["dates"].append(pillar_date)
            bucket["dfs"].append(df)

    curves: Dict[str, IRCurve] = {}
    for key, data in buckets.items():
        curves[key] = IRCurve(
            valuation_date=data["curve_date"],
            dates=data["dates"],
            discount_factors=data["dfs"],
            day_count_convention=day_count_convention,
            interpolation_method=interpolation_method,
        )

    return curves


# ------------------------------------------------------------------ #
# Fixings loader                                                      #
# ------------------------------------------------------------------ #

def load_fixings(filepath: str) -> Dict[date, float]:
    """
    Load a SAIBOR fixing history CSV and return a date-keyed dictionary.

    CSV columns expected
    --------------------
    Date          : mm/dd/yyyy  - fixing date
    <rate column> : float       - fixing rate in percent (e.g. 5.37282 = 5.37282%)
                                  The rate column name is detected automatically
                                  (second column, whatever its header).

    Duplicate dates are resolved by keeping the last occurrence.

    Parameters
    ----------
    filepath : str  - path to the CSV file (e.g. '3m_fixings.csv')

    Returns
    -------
    dict[date, float]
        e.g. { date(2025, 12, 31): 4.85925, date(2026, 1, 4): 4.87343, ... }
        Rates are stored as-is in percent (divide by 100 when pricing).
    """
    fixings: Dict[date, float] = {}

    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # Rate column = whichever header is not 'Date'
        rate_col = next(col for col in reader.fieldnames if col.strip() != "Date")
        for row in reader:
            fixing_date = _parse_date(row["Date"])
            rate        = float(row[rate_col])
            fixings[fixing_date] = rate   # last entry wins on duplicates

    return fixings
