# cash_flow_generator.py
# Written by Peter Allen - R&C
# 10 April 2026
#
# Generates IRS cashflow schedules (fixed or floating leg) adjusted for
# the Saudi Arabia public holiday calendar.
#
# Saudi weekend: Friday & Saturday
# Saudi holidays: approximated via the standard Islamic/Saudi public
# holiday set. For production use, replace SAUDI_HOLIDAYS with a
# complete authoritative list sourced from Tadawul / SAMA.
#
# Output CSV columns:
#   Fixed leg : StartDate, EndDate, PaymentDate
#   Float leg : StartDate, EndDate, ResetDate, PaymentDate
#
# Date format: M/D/YYYY  (matches existing instrument files)

from __future__ import annotations

import csv
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Tuple


# ------------------------------------------------------------------ #
# Saudi Arabia holiday calendar                                        #
# ------------------------------------------------------------------ #
# Weekend: Friday (4) and Saturday (5) — isoweekday() 5 and 6
# Holidays below cover 2024-2040.  Extend as needed.
# Dates are based on published Saudi Gregorian equivalents.
# Ramadan / Eid dates are approximate — update with confirmed dates.

_SAUDI_HOLIDAYS: set[date] = {
    # ── 2024 ──────────────────────────────────────────────────────
    date(2024, 2, 11),   # Founding Day
    date(2024, 4, 9),    # Eid Al-Fitr (approx)
    date(2024, 4, 10),
    date(2024, 4, 11),
    date(2024, 6, 16),   # Eid Al-Adha (approx)
    date(2024, 6, 17),
    date(2024, 6, 18),
    date(2024, 6, 19),
    date(2024, 9, 23),   # National Day

    # ── 2025 ──────────────────────────────────────────────────────
    date(2025, 2, 11),   # Founding Day
    date(2025, 3, 30),   # Eid Al-Fitr (approx)
    date(2025, 3, 31),
    date(2025, 4, 1),
    date(2025, 6, 6),    # Eid Al-Adha (approx)
    date(2025, 6, 7),
    date(2025, 6, 8),
    date(2025, 6, 9),
    date(2025, 9, 23),   # National Day

    # ── 2026 ──────────────────────────────────────────────────────
    date(2026, 2, 11),   # Founding Day
    date(2026, 3, 20),   # Eid Al-Fitr (approx)
    date(2026, 3, 21),
    date(2026, 3, 22),
    date(2026, 5, 27),   # Eid Al-Adha (approx)
    date(2026, 5, 28),
    date(2026, 5, 29),
    date(2026, 5, 30),
    date(2026, 9, 23),   # National Day

    # ── 2027 ──────────────────────────────────────────────────────
    date(2027, 2, 11),
    date(2027, 3, 9),    # Eid Al-Fitr (approx)
    date(2027, 3, 10),
    date(2027, 3, 11),
    date(2027, 5, 16),   # Eid Al-Adha (approx)
    date(2027, 5, 17),
    date(2027, 5, 18),
    date(2027, 5, 19),
    date(2027, 9, 23),

    # ── 2028 ──────────────────────────────────────────────────────
    date(2028, 2, 11),
    date(2028, 2, 26),   # Eid Al-Fitr (approx)
    date(2028, 2, 27),
    date(2028, 2, 28),
    date(2028, 5, 5),    # Eid Al-Adha (approx)
    date(2028, 5, 6),
    date(2028, 5, 7),
    date(2028, 5, 8),
    date(2028, 9, 23),

    # ── 2029 ──────────────────────────────────────────────────────
    date(2029, 2, 11),
    date(2029, 2, 14),   # Eid Al-Fitr (approx)
    date(2029, 2, 15),
    date(2029, 2, 16),
    date(2029, 4, 24),   # Eid Al-Adha (approx)
    date(2029, 4, 25),
    date(2029, 4, 26),
    date(2029, 4, 27),
    date(2029, 9, 23),

    # ── 2030 ──────────────────────────────────────────────────────
    date(2030, 2, 11),
    date(2030, 2, 3),    # Eid Al-Fitr (approx)
    date(2030, 2, 4),
    date(2030, 2, 5),
    date(2030, 4, 13),   # Eid Al-Adha (approx)
    date(2030, 4, 14),
    date(2030, 4, 15),
    date(2030, 4, 16),
    date(2030, 9, 23),

    # ── 2031-2040: National Day + Founding Day (holidays confirmed) ─
    # Eid dates from 2031 onward use best-estimate; replace with
    # confirmed dates when available.
    date(2031, 2, 11), date(2031, 9, 23),
    date(2032, 2, 11), date(2032, 9, 23),
    date(2033, 2, 11), date(2033, 9, 23),
    date(2034, 2, 11), date(2034, 9, 23),
    date(2035, 2, 11), date(2035, 9, 23),
    date(2036, 2, 11), date(2036, 9, 23),
    date(2037, 2, 11), date(2037, 9, 23),
    date(2038, 2, 11), date(2038, 9, 23),
    date(2039, 2, 11), date(2039, 9, 23),
    date(2040, 2, 11), date(2040, 9, 23),
}


# ------------------------------------------------------------------ #
# Business day helpers                                                 #
# ------------------------------------------------------------------ #

def _is_saudi_business_day(d: date) -> bool:
    """Return True if d is a Saudi business day (Sun-Thu, not a holiday)."""
    # isoweekday: Mon=1 ... Sun=7; Saudi weekend is Fri(5) and Sat(6)
    return d.isoweekday() not in (5, 6) and d not in _SAUDI_HOLIDAYS


def _adjust_following(d: date) -> date:
    """Move d forward until it falls on a Saudi business day."""
    while not _is_saudi_business_day(d):
        d += timedelta(days=1)
    return d


def _adjust_modified_following(d: date) -> date:
    """
    Modified Following: move forward unless that crosses into the next
    calendar month, in which case move backward.
    """
    original_month = d.month
    candidate = d
    while not _is_saudi_business_day(candidate):
        candidate += timedelta(days=1)
    if candidate.month != original_month:
        candidate = d
        while not _is_saudi_business_day(candidate):
            candidate -= timedelta(days=1)
    return candidate


def _add_business_days(d: date, n: int) -> date:
    """
    Return the date n business days before (n<0) or after (n>0) d.
    """
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    current = d
    while remaining > 0:
        current += timedelta(days=step)
        if _is_saudi_business_day(current):
            remaining -= 1
    return current


def _reset_date(period_start: date, spot_lag: int = 2) -> date:
    """
    SAIBOR/LIBOR-style reset date:
      reset = spot_lag business days BEFORE the period start date.

    The fixing is set on the reset date and applies from period_start.
    """
    return _add_business_days(period_start, -spot_lag)


# ------------------------------------------------------------------ #
# Period frequency helpers                                             #
# ------------------------------------------------------------------ #

_FREQUENCY_TO_MONTHS = {
    "1M":  1,
    "3M":  3,
    "6M":  6,
    "12M": 12,
    "1Y":  12,
}


def _period_delta(frequency: str) -> relativedelta:
    months = _FREQUENCY_TO_MONTHS.get(frequency.upper())
    if months is None:
        raise ValueError(
            f"Unsupported frequency '{frequency}'. "
            f"Supported: {list(_FREQUENCY_TO_MONTHS.keys())}"
        )
    return relativedelta(months=months)


# ------------------------------------------------------------------ #
# Schedule generation                                                  #
# ------------------------------------------------------------------ #

def _generate_unadjusted_end_dates(
    start_date: date,
    end_date:   date,
    frequency:  str,
    stub_type:  str,
) -> List[date]:
    """
    Generate the unadjusted period end dates (= unadjusted payment dates)
    between start_date and end_date.

    stub_type:
        'FRONT' — short stub at the beginning (front stub)
        'BACK'  — short stub at the end       (back stub)
        'NONE'  — assume schedule fits exactly, no stub
    """
    delta = _period_delta(frequency)
    stub  = stub_type.upper()

    if stub in ("BACK", "NONE"):
        # Roll forward from start_date
        dates = []
        current = start_date
        while True:
            nxt = current + delta
            if nxt >= end_date:
                dates.append(end_date)
                break
            dates.append(nxt)
            current = nxt
        return dates

    elif stub == "FRONT":
        # Roll backward from end_date, then reverse
        dates = []
        current = end_date
        while True:
            prev = current - delta
            if prev <= start_date:
                dates.append(start_date)   # front stub boundary
                break
            dates.append(current)
            current = prev
        dates.reverse()
        # dates now contains the unadjusted end-of-period boundaries
        # after the front stub; append end_date if not already there
        if dates[-1] != end_date:
            dates.append(end_date)
        return dates

    else:
        raise ValueError(f"stub_type must be 'FRONT', 'BACK', or 'NONE'. Got '{stub_type}'.")


def _build_periods(
    start_date: date,
    end_date:   date,
    frequency:  str,
    stub_type:  str,
) -> List[Tuple[date, date]]:
    """
    Return list of (period_start, period_end) in unadjusted dates.
    """
    end_dates = _generate_unadjusted_end_dates(start_date, end_date, frequency, stub_type)
    periods   = []
    prev      = start_date
    for ed in end_dates:
        periods.append((prev, ed))
        prev = ed
    return periods


# ------------------------------------------------------------------ #
# Public API                                                           #
# ------------------------------------------------------------------ #

def irs_cashflow_generator(
    start_date:       date,
    end_date:         date,
    period_frequency: str,
    stub_type:        str,
    is_fixed_leg:     bool,
    output_path:      str | None = None,
    spot_lag:         int        = 2,
) -> List[dict]:
    """
    Generate an IRS cashflow schedule adjusted for the Saudi Arabia
    business day calendar and write it to a CSV file.

    Parameters
    ----------
    start_date       : effective / start date of the IRS
    end_date         : maturity date of the IRS
    period_frequency : coupon frequency — '1M', '3M', '6M', '12M' / '1Y'
    stub_type        : 'FRONT', 'BACK', or 'NONE'
    is_fixed_leg     : True  → fixed leg  (StartDate, EndDate, PaymentDate)
                       False → float leg  (StartDate, EndDate, ResetDate, PaymentDate)
    output_path      : file path for the output CSV.
                       If None, prints to stdout only.
    spot_lag         : business days before period start for the reset date
                       (float leg only). Default 2 (SAIBOR convention).

    Returns
    -------
    List of dicts, one per cashflow period. Keys match the CSV columns.

    Date format in CSV: M/D/YYYY  (no leading zeros — matches instrument files)
    """
    stub_type        = stub_type.upper()
    period_frequency = period_frequency.upper()

    periods = _build_periods(start_date, end_date, period_frequency, stub_type)

    rows: List[dict] = []

    for (unadj_start, unadj_end) in periods:
        # Period start: apply Modified Following to the unadjusted start
        # (the very first period start = IRS effective date, left as-is
        #  unless it itself is a non-business day)
        adj_start   = _adjust_modified_following(unadj_start)
        adj_end     = _adjust_modified_following(unadj_end)
        adj_payment = _adjust_modified_following(unadj_end)

        if is_fixed_leg:
            rows.append({
                "StartDate":   adj_start,
                "EndDate":     adj_end,
                "PaymentDate": adj_payment,
            })
        else:
            # Reset date = spot_lag business days before adj_start
            adj_reset = _reset_date(adj_start, spot_lag=spot_lag)
            rows.append({
                "StartDate":   adj_start,
                "EndDate":     adj_end,
                "ResetDate":   adj_reset,
                "PaymentDate": adj_payment,
            })

    # ── Write CSV ────────────────────────────────────────────────
    _fmt = lambda d: f"{d.month}/{d.day}/{d.year}"   # M/D/YYYY, no leading zeros

    if is_fixed_leg:
        fieldnames = ["StartDate", "EndDate", "PaymentDate"]
    else:
        fieldnames = ["StartDate", "EndDate", "ResetDate", "PaymentDate"]

    if output_path is not None:
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _fmt(v) for k, v in row.items()})
        print(f"Written {len(rows)} periods to: {output_path}")
    else:
        # Pretty-print to stdout
        header = ",".join(fieldnames)
        print(header)
        for row in rows:
            print(",".join(_fmt(row[f]) for f in fieldnames))

    return rows


# ------------------------------------------------------------------ #
# Example / smoke-test (run this file directly)                        #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    from datetime import date

    print("=" * 55)
    print("H1 FIXED LEG  (annual, 2026-01-04 to 2036-01-04)")
    print("=" * 55)
    irs_cashflow_generator(
        start_date       = date(2026, 1, 4),
        end_date         = date(2039, 1, 4),
        period_frequency = "12M",
        stub_type        = "NONE",
        is_fixed_leg     = True,
        output_path      = None,
    )

    print()
    print("=" * 55)
    print("H1 FLOAT LEG  (6M, 2026-01-04 to 2036-01-04)")
    print("=" * 55)
    irs_cashflow_generator(
        start_date       = date(2026, 1, 4),
        end_date         = date(2039, 1, 4),
        period_frequency = "6M",
        stub_type        = "NONE",
        is_fixed_leg     = False,
        output_path      = None,
    )
