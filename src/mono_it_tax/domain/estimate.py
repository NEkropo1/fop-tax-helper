"""Indicative taxes for an arbitrary set of months (no declaration help, no previous period)."""

from dataclasses import dataclass
from decimal import Decimal

from mono_it_tax.config.rules import Rules
from mono_it_tax.domain.money import round_money


@dataclass(frozen=True)
class RateEstimate:
    """The single tax and the grand total if the taxpayer's single-tax rate is `rate`."""

    rate: Decimal
    single_tax: Decimal
    total: Decimal


@dataclass(frozen=True)
class Estimate:
    """Levy and ESV do not depend on the single-tax rate, so only that part is listed per rate."""

    income_uah: Decimal
    military_levy: Decimal
    esv: Decimal
    months: int
    by_rate: tuple[RateEstimate, ...]


def estimate(income_uah: Decimal, months: int, rules: Rules) -> Estimate:
    income = round_money(income_uah)
    levy = round_money(income * rules.military_levy_rate)
    esv = round_money(rules.esv_monthly * months)
    by_rate = []
    for rate in rules.estimate_rates:
        single_tax = round_money(income * rate)
        by_rate.append(RateEstimate(rate, single_tax, single_tax + levy + esv))
    return Estimate(
        income_uah=income, military_levy=levy, esv=esv, months=months, by_rate=tuple(by_rate)
    )
