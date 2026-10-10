"""Money and identifier-masking constants."""

from decimal import Decimal

MINOR_UNITS_PER_MAJOR = 100  # kopiykas per hryvnia, cents per dollar
MONEY_QUANTUM = Decimal("0.01")
PAN_VISIBLE_HEAD = 4
PAN_VISIBLE_TAIL = 4
MASK_CHAR = "*"
HANDLE_LENGTH = 10
