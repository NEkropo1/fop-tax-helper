"""Indicative estimate screen text (months mode)."""

from mono_it_tax.config.rules import Rules
from mono_it_tax.copy.declaration_uk import format_money, sources_lines
from mono_it_tax.domain.estimate import Estimate

HEAD_LINES = ("Дохід за обрані місяці: {income} грн",)
RATE_LINE = "Єдиний податок ({rate:.0%}): {single_tax} грн; разом із ВЗ та ЄСВ: {total} грн"
TAIL_LINES = (
    "Військовий збір ({levy_rate:.0%}): {military_levy} грн",
    "ЄСВ (мінімальний, {months} міс.): {esv} грн",
    "Це орієнтовний розрахунок.",
)


def format_estimate(est: Estimate, rules: Rules) -> str:
    values = {
        "income": format_money(est.income_uah),
        "levy_rate": rules.military_levy_rate,
        "military_levy": format_money(est.military_levy),
        "months": est.months,
        "esv": format_money(est.esv),
    }
    rate_lines = [
        RATE_LINE.format(
            rate=item.rate, single_tax=format_money(item.single_tax), total=format_money(item.total)
        )
        for item in est.by_rate
    ]
    head = [line.format(**values) for line in HEAD_LINES]
    tail = [line.format(**values) for line in TAIL_LINES]
    return "\n".join([*head, *rate_lines, *tail, *sources_lines(rules)])
