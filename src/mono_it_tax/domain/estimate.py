"""Indicative taxes for an arbitrary set of months (no declaration help, no previous period)."""

from dataclasses import dataclass
from decimal import Decimal

from mono_it_tax.config.rules import Rules
from mono_it_tax.domain.money import round_money


@dataclass(frozen=True)
class Estimate:
    income_uah: Decimal
    single_tax: Decimal
    military_levy: Decimal
    esv: Decimal
    months: int

    @property
    def total(self) -> Decimal:
        return self.single_tax + self.military_levy + self.esv


def estimate(income_uah: Decimal, months: int, rules: Rules) -> Estimate:
    income = round_money(income_uah)
    return Estimate(
        income_uah=income,
        single_tax=round_money(income * rules.single_tax.rate),
        military_levy=round_money(income * rules.military_levy_rate),
        esv=round_money(rules.esv_monthly * months),
        months=months,
    )
