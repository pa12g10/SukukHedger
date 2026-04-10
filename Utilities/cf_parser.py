# cf_parser.py
# Written by Peter Allen - R&C
# 10 April 2026
# Loads fixed and floating cashflow schedule CSVs into structured objects.

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional


# ------------------------------------------------------------------ #
# Data classes                                                        #
# ------------------------------------------------------------------ #

@dataclass
class FixedCashflow:
    """
    A single period on a fixed leg.

    Attributes
    ----------
    start_date   : date  – accrual start
    end_date     : date  – accrual end
    payment_date : date  – cash payment date
    """
    start_date:   date
    end_date:     date
    payment_date: date


@dataclass
class FloatCashflow:
    """
    A single period on a floating leg.

    Attributes
    ----------
    start_date   : date  – accrual start
    end_date     : date  – accrual end
    reset_date   : date  – fixing / reset date
    payment_date : date  – cash payment date
    """
    start_date:   date
    end_date:     date
    reset_date:   date
    payment_date: date


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _parse_date(s: str) -> date:
    """Parse mm/dd/yyyy date string to datetime.date."""
    return datetime.strptime(s.strip(), "%m/%d/%Y").date()


# ------------------------------------------------------------------ #
# Public loaders                                                      #
# ------------------------------------------------------------------ #

def load_fixed_cashflows(filepath: str) -> List[FixedCashflow]:
    """
    Load a fixed-leg cashflow schedule CSV.

    Expected columns (case-sensitive)
    ----------------------------------
    StartDate, EndDate, PaymentDate

    Parameters
    ----------
    filepath : str  – path to CSV file

    Returns
    -------
    list[FixedCashflow]  – one entry per coupon period, ordered as in file
    """
    cashflows: List[FixedCashflow] = []
    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cashflows.append(
                FixedCashflow(
                    start_date=_parse_date(row["StartDate"]),
                    end_date=_parse_date(row["EndDate"]),
                    payment_date=_parse_date(row["PaymentDate"]),
                )
            )
    return cashflows


def load_float_cashflows(filepath: str) -> List[FloatCashflow]:
    """
    Load a floating-leg cashflow schedule CSV.

    Expected columns (case-sensitive)
    ----------------------------------
    StartDate, EndDate, ResetDate, PaymentDate

    Parameters
    ----------
    filepath : str  – path to CSV file

    Returns
    -------
    list[FloatCashflow]  – one entry per coupon period, ordered as in file
    """
    cashflows: List[FloatCashflow] = []
    with open(filepath, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cashflows.append(
                FloatCashflow(
                    start_date=_parse_date(row["StartDate"]),
                    end_date=_parse_date(row["EndDate"]),
                    reset_date=_parse_date(row["ResetDate"]),
                    payment_date=_parse_date(row["PaymentDate"]),
                )
            )
    return cashflows
