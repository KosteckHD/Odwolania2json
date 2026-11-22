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
    """Numer rachunku tak jak w dokumencie, bez spacji: z przedrostkiem „PL”, jeśli dokument go ma.

    UZP (21.11): w zbiorze testowym numer jest zapisany jak w dokumencie; brak „PL”
    w części wzorców treningowych to ich błąd.
    """
    compact = "".join(value.split()).upper()
    if re.fullmatch(r"(?:PL)?[0-9]{26}", compact):
        return compact
    return value


def normalize_bzp(value: str) -> str:
    """Numer ogłoszenia BZP w formacie wzorców UZP: `RRRR/BZP########` (opcjonalnie `/##`), bez spacji."""
    match = re.fullmatch(r"([0-9]{4})\s*/\s*BZP\s*([0-9]{8})(?:\s*/\s*([0-9]{2}))?", value.strip(), re.IGNORECASE)
    if not match:
        return value
    year, number, correction = match.groups()
    return f"{year}/BZP{number}" + (f"/{correction}" if correction else "")


def normalize_ted(value: str) -> str:
    match = re.fullmatch(r"\s*([0-9]{4})\s*[/\-]\s*[Ss]\s*[0-9]{1,3}\s*-\s*([0-9]{6})\s*", value)
    if match:
        return f"{match.group(2)}-{match.group(1)}"
    return value


POLISH_MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)


def normalize_date(value: str) -> str | None:
    """Data ISO z `RRRR-MM-DD`, `DD.MM.RRRR` (też `/` i `-`) albo `D miesiąca RRRR` (dopełniacz)."""
    value = " ".join(value.split())
    match = re.fullmatch(r"([0-9]{1,2})([./-])([0-9]{1,2})\2([0-9]{4})", value)
    if match:
        day, _, month, year = match.groups()
        value = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    match = re.fullmatch(r"([0-9]{1,2}) (\w+) ([0-9]{4})(?: r\.?| roku)?", value)
    if match and match.group(2).lower() in POLISH_MONTHS:
        day, month, year = match.groups()
        value = f"{year}-{POLISH_MONTHS.index(month.lower()) + 1:02d}-{day.zfill(2)}"
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
