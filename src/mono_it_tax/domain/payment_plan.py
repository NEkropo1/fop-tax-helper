"""What to pay and until when for the quarter a period adds. Pure; the human pays in the cabinet."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from mono_it_tax.config.constants.time import MONTHS_IN_YEAR
from mono_it_tax.config.enums import Tax, Weekday
from mono_it_tax.config.rules import Rules
from mono_it_tax.domain.declaration import DeclarationRows
from mono_it_tax.domain.money import round_money
from mono_it_tax.domain.periods import period_end


def next_working_day(day: date) -> date:
    """Weekend -> following Monday. Public holidays are intentionally not modelled."""
    while day.weekday() >= Weekday.SATURDAY:
        day += timedelta(days=1)
    return day


@dataclass(frozen=True)
class PlannedPayment:
    tax: Tax
    amount: Decimal
    due: date
    budget_code: str


@dataclass(frozen=True)
class PaymentPlan:
    declaration_due: date
    payments: tuple[PlannedPayment, ...]


def build_plan(rows: DeclarationRows, rules: Rules) -> PaymentPlan:
    deadlines = rules.deadlines
    quarter_end = period_end(rows.period, rows.year)
    tax_due = next_working_day(
        quarter_end + timedelta(days=deadlines.single_tax_days_after_quarter_end)
    )
    esv_year = quarter_end.year + (quarter_end.month == MONTHS_IN_YEAR)
    esv_month = quarter_end.month % MONTHS_IN_YEAR + 1
    esv_due = next_working_day(date(esv_year, esv_month, deadlines.esv_day_of_next_month))
    codes = rules.budget_codes
    return PaymentPlan(
        declaration_due=next_working_day(
            quarter_end + timedelta(days=deadlines.declaration_days_after_quarter_end)
        ),
        payments=(
            PlannedPayment(Tax.ESV, round_money(rules.esv_quarterly), esv_due, codes[Tax.ESV]),
            PlannedPayment(Tax.SINGLE_TAX, rows.row_14, tax_due, codes[Tax.SINGLE_TAX]),
            PlannedPayment(Tax.MILITARY_LEVY, rows.row_25, tax_due, codes[Tax.MILITARY_LEVY]),
        ),
    )
