# Utilities
# Written by Peter Allen - R&C
# 03 April 2026
# Pricing utilities for Hedge Effectiveness Calculation

from datetime import date


DAY_COUNT_ALIASES = {
    "ACT/360": "ACT/360", "ACT360": "ACT/360", "A/360": "ACT/360",
    "ACT/365": "ACT/365", "ACT365": "ACT/365", "A/365": "ACT/365",
    "30/360":  "30/360",  "30E/360": "30/360",
}


def _days360_isma(d1: date, d2: date) -> int:
    """30/360 ISMA day count between two dates."""
    y1, m1, dd1 = d1.year, d1.month, d1.day
    y2, m2, dd2 = d2.year, d2.month, d2.day
    if dd1 == 31: dd1 = 30
    if dd2 == 31: dd2 = 30
    return 360 * (y2 - y1) + 30 * (m2 - m1) + (dd2 - dd1)


def year_fraction(start_date: date, end_date: date, day_count: str) -> float:
    """
    Calculate the year fraction between two dates.

    Parameters
    ----------
    start_date : date
    end_date   : date
    day_count  : str
        Supported conventions: 'ACT/360', 'ACT/365', '30/360' (and common aliases).

    Returns
    -------
    float

    Raises
    ------
    ValueError
        If end_date < start_date or the day_count convention is unknown.
    """
    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) must be >= start_date ({start_date}).")

    convention = DAY_COUNT_ALIASES.get(day_count.strip().upper())
    if convention is None:
        raise ValueError(f"Unknown day count convention: '{day_count}'. "
                         f"Supported: {list(DAY_COUNT_ALIASES.keys())}")

    days = (end_date - start_date).days

    if convention == "ACT/360":
        return days / 360.0
    elif convention == "ACT/365":
        return days / 365.0
    elif convention == "30/360":
        return _days360_isma(start_date, end_date) / 360.0
