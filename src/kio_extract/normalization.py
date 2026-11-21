import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from .contracts import JsonValue


def normalize_text(value: str) -> str | None:
    return " ".join(value.split()) or None


def normalize_digits(value: str) -> str | None:
    value = re.sub(r"[\s-]", "", value)
    return value if re.fullmatch(r"[0-9]+", value) else None


def normalize_polish_bank_account(value: str) -> str:
    compact = "".join(value.split()).replace("\u200b", "").replace("\ufeff", "").upper()
    if re.fullmatch(r"PL[0-9]{26}", compact):
        return compact[2:]
    if re.fullmatch(r"[0-9]{26}", compact):
        return compact
    return value


def has_valid_polish_bank_checksum(value: str) -> bool:
    """Check the NRB/IBAN control digits using the NBP MOD-97 procedure."""
    compact = "".join(value.split()).replace("\u200b", "").replace("\ufeff", "").upper()
    if compact.startswith("PL"):
        compact = compact[2:]
    if not re.fullmatch(r"[0-9]{26}", compact):
        return False
    rearranged = compact[2:] + "2521" + compact[:2]
    return int(rearranged) % 97 == 1


def normalize_ted(value: str) -> str:
    match = re.fullmatch(r"\s*([0-9]{4})\s*[/\-]\s*[Ss]\s*[0-9]{1,3}\s*-\s*([0-9]{6})\s*", value)
    if match:
        return f"{match.group(2)}-{match.group(1)}"
    return value


def normalize_date(value: str) -> str | None:
    value = value.strip()
    match = re.fullmatch(r"([0-9]{1,2})([./-])([0-9]{1,2})\2([0-9]{4})", value)
    if match:
        day, _, month, year = match.groups()
        value = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def normalize_amount(value: str) -> float | None:
    value = value.strip()
    if not re.fullmatch(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:[^\S\r\n][0-9]{3})+)(?:[,.][0-9]{2})?", value):
        return None
    amount = float(Decimal("".join(value.split()).replace(",", ".")))
    return amount if abs(amount) != float("inf") else None


NORMALIZERS: dict[str, Callable[[str], JsonValue]] = {
    "text": normalize_text,
    "digits": normalize_digits,
    "iso_date": normalize_date,
    "amount": normalize_amount,
}
