"""Declaration help texts (Ukrainian): what to check, what to type, what appears by itself, what to
pay. Order and wording follow what the cabinet really does (checked 2026-10) and the
Smokovych video. Every row number comes from the rules file, every amount from the state objects.
"""

from decimal import Decimal

from mono_it_tax.config.constants.time import QUARTERS_IN_YEAR
from mono_it_tax.config.enums import Period, Tax
from mono_it_tax.config.rules import Rules
from mono_it_tax.domain.declaration import DeclarationRows
from mono_it_tax.domain.money import round_money
from mono_it_tax.domain.payment_plan import PaymentPlan
from mono_it_tax.domain.periods import increment_months, previous_period

PERIOD_LABELS: dict[Period, str] = {
    Period.Q1: "I квартал",
    Period.H1: "півріччя",
    Period.M9: "три квартали",
    Period.Y: "рік",
}
TAX_LABELS: dict[Tax, str] = {
    Tax.ESV: "ЄСВ (мінімальний, за квартал)",
    Tax.SINGLE_TAX: "Єдиний податок",
    Tax.MILITARY_LEVY: "Військовий збір",
}
MONTH_NAMES = (
    "січень", "лютий", "березень", "квітень", "травень", "червень",
    "липень", "серпень", "вересень", "жовтень", "листопад", "грудень",
)  # fmt: skip
NOTHING_TO_PAY = "платити нічого"
FIRST_PERIOD_NOTE = "Це перша декларація року: попередня не потрібна."

PREVIOUS_REPORT_REQUEST = (
    "Відкрийте {cabinet} → «Перегляд звітності», оберіть {year} рік і відкрийте свою ПОПЕРЕДНЮ "
    "декларацію {form} ({previous} {year}). Перепишіть звідти суми (грн, коп):\n"
    "  - рядок {income_row} — обсяг доходу;\n"
    "  - рядок {row_15} — має бути 0 (інакше цей інструмент не підходить);\n"
    "  - рядок {tax_total} — єдиний податок за період;\n"
    "  - рядок {levy_total} — військовий збір за період."
)

FILL_HEADER = "Створіть декларацію {form}: період «{period} {year}», тип «Звітна»."
STEP_CHECK_OWN_DATA = (
    "1. Одразу після створення перевірте, що підтягнулись ваші дані: у полі {office} — ваша "
    "податкова (за місцем реєстрації), у полі {taxpayer} — ваші ПІБ, далі адреса, ІПН і КВЕД. "
    "Якщо щось не так — не продовжуйте: оновіть сторінку або створіть декларацію заново."
)
STEP_PREFILLED = (
    "2. Перевірте підтягнуті рядки. Зазвичай підтягуються лише два, решта порожні: рядок "
    "{tax_previous} = {row_13} (це рядок {tax_total} попередньої декларації) і рядок "
    "{levy_previous} = {row_24} (це рядок {levy_total} попередньої). Якщо вони не підтягнулись — "
    "оновіть сторінку або створіть декларацію заново; якщо все одно порожні — впишіть їх вручну "
    "саме з цих рядків попередньої декларації."
)
STEP_PREFILLED_FIRST = (
    "2. Це перша декларація року: рядки {tax_previous} і {levy_previous} мають бути порожні "
    "(попереднього періоду немає)."
)
STEP_EMPLOYEES = (
    "3. У пункті {employees} (фактична чисельність найманих працівників) впишіть кількість: для "
    "більшості ФОП, і для цього застосунку, це 0."
)
STEP_INCOME = (
    "4. Далі заповнюйте рядок {income_row} (розділ IV, ставка {rate:.0%}; {regime_note}): впишіть "
    "загальний дохід за ВЕСЬ звітний період з початку року ({period_label}) = {income} грн. "
    "{income_note}"
)
INCOME_NOTE_NONE_NEW = (
    "Нового доходу за {new_months} немає, тому сума та сама, що в попередній декларації."
)
INCOME_NOTE_NEW = (
    "Це дохід попередньої декларації ({previous_income}) плюс новий за {new_months} ({new_income})."
)
INCOME_NOTE_FIRST = "Це дохід за {new_months}."
STEP_AUTOFILL = "5. Одразу після введення кабінет сам заповнить рядки:"
AUTOFILL_ALWAYS = (
    "   - {total_income} (усього доходу) = {income}",
    "   - {tax_row} (податок за ставкою {rate:.0%}) = {tax_at_rate}",
    "   - {tax_total} (нараховано всього за період) = {row_12}",
    "   - {levy_total} (військовий збір за період) = {row_23}",
)
AUTOFILL_TAX_DUE = (
    "   - {tax_due_base} (до сплати за підсумками періоду, {tax_total} - {tax_previous}) "
    "= {row_14}",
    "   - {tax_due} (загальна сума єдиного податку до сплати, {tax_due_base} + {tax_due_extra}) "
    "= {row_14}",
)
AUTOFILL_TAX_DUE_EMPTY = (
    "   - рядки {tax_due_base} і {tax_due} лишаються порожніми: це те саме, що 0,00 — єдиного "
    "податку до сплати за цей період немає."
)
AUTOFILL_LEVY_DUE = (
    "   - {levy_due} (військовий збір до сплати, {levy_total} - {levy_previous}) = {row_25}"
)
AUTOFILL_LEVY_DUE_EMPTY = (
    "   - рядок {levy_due} лишається порожнім: це те саме, що 0,00 — військового збору до сплати "
    "немає."
)
AUTOFILL_WARNING = (
    "   Якщо цифри відрізняються — НЕ подавайте декларацію: перевірте введені дані (і що рядок "
    "{tax_previous} справді дорівнює рядку {tax_total} попередньої декларації)."
)
STEP_EMPTY_ROWS = (
    "6. Решта рядків мають лишитись порожніми або 0,00: {empty_rows}. Якщо в якомусь з них щось "
    "з'явилось — НЕ подавайте декларацію."
)
ESV_ROW_NOT_NEEDED = (
    "Рядок {esv_due} і Додаток 1 (ЄСВ) у цій декларації не заповнюються: вони потрібні лише в "
    "річній декларації. ЄСВ просто сплачується (див. платежі нижче)."
)
ESV_ROW_ANNUAL = (
    "Це річна декларація: додайте Додаток 1 (ЄСВ) і перенесіть його підсумок (розділ 9, рядок "
    "«Усього», графа 4) у рядок {esv_due}. Якщо ви сплачували мінімальний ЄСВ усі 12 місяців, "
    "очікуване значення — {esv_year} грн. Застосунок цей додаток не веде: звіряйте з ним."
)
FILL_DEADLINE = "Подати декларацію до {declaration_due:%d.%m.%Y}."
FILL_PAYMENTS_HEADER = (
    "Платежі (рахунки з реквізитами генеруються в кабінеті платника — {tax_account}, ми їх не "
    "автоматизуємо):"
)
FILL_PAYMENT_LINE = "   - {label}: {what}, до {due:%d.%m.%Y} (код платежу {code})"
FOOTER = (
    "Відео-розбір заповнення декларації: {video}",
    "Інформація може бути неактуальною: звіряйтесь з каналами — {channels}.",
    "Помітили неактуальне? Напишіть автору: {linkedin}",
    "Правила станом на {updated_on:%d.%m.%Y} (версія {version}). {disclaimer}",
)

Values = dict[str, object]


def format_money(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", " ")


def previous_report_request(previous: Period | None, year: int, rules: Rules) -> str:
    if previous is None:
        return FIRST_PERIOD_NOTE
    return PREVIOUS_REPORT_REQUEST.format(
        cabinet=rules.links.cabinet,
        year=year,
        form=rules.declaration.form,
        previous=PERIOD_LABELS[previous],
        income_row=rules.single_tax.income_row,
        row_15=rules.declaration.rows.income_15,
        tax_total=rules.declaration.rows.tax_total,
        levy_total=rules.declaration.rows.levy_total,
    )


def _months_label(period: Period, year: int) -> str:
    months = increment_months(period, year)
    return f"{MONTH_NAMES[months[0].month - 1]}–{MONTH_NAMES[months[-1].month - 1]}"


def _values(rows: DeclarationRows, rules: Rules) -> Values:
    r, fields = rules.declaration.rows, rules.declaration.fields
    return {
        "office": fields.office,
        "taxpayer": fields.taxpayer,
        "employees": fields.employees,
        "income_row": rules.single_tax.income_row,
        "tax_row": rules.single_tax.tax_row,
        "rate": rules.single_tax.rate,
        "regime_note": rules.single_tax.note,
        "row_15": r.income_15,
        "total_income": r.total_income,
        "tax_total": r.tax_total,
        "tax_previous": r.tax_previous,
        "tax_due_base": r.tax_due_base,
        "tax_due_extra": r.tax_due_extra,
        "tax_due": r.tax_due,
        "esv_due": r.esv_due,
        "levy_total": r.levy_total,
        "levy_previous": r.levy_previous,
        "levy_due": r.levy_due,
        "empty_rows": ", ".join(rules.declaration.empty_rows),
        "income": format_money(rows.income),
        "tax_at_rate": format_money(rows.tax_at_rate),
        "row_12": format_money(rows.row_12),
        "row_13": format_money(rows.row_13),
        "row_14": format_money(rows.row_14),
        "row_23": format_money(rows.row_23),
        "row_24": format_money(rows.row_24),
        "row_25": format_money(rows.row_25),
        "period_label": PERIOD_LABELS[rows.period],
        "new_months": _months_label(rows.period, rows.year),
        "new_income": format_money(rows.new_income),
        "previous_income": format_money(rows.income - rows.new_income),
    }


def _income_note(rows: DeclarationRows, values: Values) -> str:
    if previous_period(rows.period) is None:  # nothing carried over: first period of the year
        return INCOME_NOTE_FIRST.format(**values)
    if rows.new_income == 0:
        return INCOME_NOTE_NONE_NEW.format(**values)
    return INCOME_NOTE_NEW.format(**values)


def _autofill_lines(rows: DeclarationRows, values: Values) -> list[str]:
    lines = [line.format(**values) for line in AUTOFILL_ALWAYS]
    if rows.row_14 > 0:
        lines.extend(line.format(**values) for line in AUTOFILL_TAX_DUE)
    else:
        lines.append(AUTOFILL_TAX_DUE_EMPTY.format(**values))
    levy_line = AUTOFILL_LEVY_DUE if rows.row_25 > 0 else AUTOFILL_LEVY_DUE_EMPTY
    lines.append(levy_line.format(**values))
    lines.append(AUTOFILL_WARNING.format(**values))
    return lines


def _esv_note(period: Period, values: Values, rules: Rules) -> str:
    """Row 21 / Додаток 1 exist only in the annual declaration."""
    if period is not Period.Y:
        return ESV_ROW_NOT_NEEDED.format(**values)
    esv_year = format_money(round_money(rules.esv_quarterly * QUARTERS_IN_YEAR))
    return ESV_ROW_ANNUAL.format(**values, esv_year=esv_year)


def fill_instructions(rows: DeclarationRows, plan: PaymentPlan, rules: Rules) -> str:
    values = _values(rows, rules)
    has_previous = previous_period(rows.period) is not None
    lines = [
        FILL_HEADER.format(
            form=rules.declaration.form, period=PERIOD_LABELS[rows.period], year=rows.year
        ),
        "",
        STEP_CHECK_OWN_DATA.format(**values),
        (STEP_PREFILLED if has_previous else STEP_PREFILLED_FIRST).format(**values),
        STEP_EMPLOYEES.format(**values),
        STEP_INCOME.format(**values, income_note=_income_note(rows, values)),
        STEP_AUTOFILL.format(**values),
        *_autofill_lines(rows, values),
        STEP_EMPTY_ROWS.format(**values),
        "",
        _esv_note(rows.period, values, rules),
        "",
        FILL_DEADLINE.format(declaration_due=plan.declaration_due),
        "",
        FILL_PAYMENTS_HEADER.format(tax_account=rules.links.tax_account),
    ]
    for item in plan.payments:
        what = NOTHING_TO_PAY if item.amount == 0 else f"{format_money(item.amount)} грн"
        lines.append(
            FILL_PAYMENT_LINE.format(
                label=TAX_LABELS[item.tax], what=what, due=item.due, code=item.budget_code
            )
        )
    channels = ", ".join(f"{c.name} ({c.url})" for c in rules.channels)
    lines.append("")
    lines.extend(
        line.format(
            video=rules.links.declaration_video,
            channels=channels,
            linkedin=rules.contact.linkedin,
            updated_on=rules.updated_on,
            version=rules.version,
            disclaimer=rules.disclaimer,
        )
        for line in FOOTER
    )
    return "\n".join(lines)
