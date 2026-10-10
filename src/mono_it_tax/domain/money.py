"""Money and identifier helpers. Decimal everywhere; one rounding function (half-up, kopiykas)."""

from decimal import ROUND_HALF_UP, Decimal

from mono_it_tax.config.constants.money import (
    MASK_CHAR,
    MINOR_UNITS_PER_MAJOR,
    MONEY_QUANTUM,
    PAN_VISIBLE_HEAD,
    PAN_VISIBLE_TAIL,
)


def minor_to_decimal(minor: int) -> Decimal:
    return Decimal(minor) / MINOR_UNITS_PER_MAJOR


def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def mask_pan(masked_pan: str) -> str:
    """'537541******1234' -> '5375********1234' (first 4 + last 4 only)."""
    digits = masked_pan.replace(" ", "")
    visible = PAN_VISIBLE_HEAD + PAN_VISIBLE_TAIL
    if len(digits) <= visible:
        return MASK_CHAR * len(digits)
    hidden = MASK_CHAR * (len(digits) - visible)
    return digits[:PAN_VISIBLE_HEAD] + hidden + digits[-PAN_VISIBLE_TAIL:]
