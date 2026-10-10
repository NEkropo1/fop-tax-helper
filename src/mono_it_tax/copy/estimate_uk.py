"""Indicative estimate screen text (months mode)."""

from mono_it_tax.config.rules import Rules
from mono_it_tax.copy.declaration_uk import format_money
from mono_it_tax.domain.estimate import Estimate

ESTIMATE_LINES = (
    "Дохід за обрані місяці: {income} грн",
    "Єдиний податок ({tax_rate:.0%}): {single_tax} грн",
    "Військовий збір ({levy_rate:.0%}): {military_levy} грн",
    "ЄСВ (мінімальний, {months} міс.): {esv} грн",
    "Разом: {total} грн",
    "Це орієнтовний розрахунок. Звіряйтесь із законом або бухгалтером: {channels}",
)


def format_estimate(est: Estimate, rules: Rules) -> str:
    channels = ", ".join(f"{c.name} ({c.url})" for c in rules.channels)
    values = {
        "income": format_money(est.income_uah),
        "tax_rate": rules.single_tax.rate,
        "single_tax": format_money(est.single_tax),
        "levy_rate": rules.military_levy_rate,
        "military_levy": format_money(est.military_levy),
        "months": est.months,
        "esv": format_money(est.esv),
        "total": format_money(est.total),
        "channels": channels,
    }
    return "\n".join(line.format(**values) for line in ESTIMATE_LINES)
