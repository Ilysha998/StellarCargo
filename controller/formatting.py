"""Форматирование величин для вывода в TUI / консоль."""

from __future__ import annotations

__all__ = [
    "plural_ru",
    "format_duration",
    "format_money",
    "format_distance",
    "format_tonnes",
]


def plural_ru(n: int, forms: tuple[str, str, str]) -> str:
    """Русская форма множественного числа: (год, года, лет)."""
    n = int(abs(n))
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return forms[0]
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return forms[1]
    return forms[2]


def format_duration(seconds: float) -> str:
    """Секунды -> «10 лет 2 месяца 3 дня» (год=365 д, месяц=30 д)."""
    total = int(round(seconds))
    if total <= 0:
        return "0 секунд"

    parts: list[str] = []
    rest = total
    has_large = False
    for size, forms in (
        (365 * 86400, ("год", "года", "лет")),
        (30 * 86400, ("месяц", "месяца", "месяцев")),
        (86400, ("день", "дня", "дней")),
        (3600, ("час", "часа", "часов")),
        (60, ("минута", "минуты", "минут")),
    ):
        n, rest = divmod(rest, size)
        if size >= 86400 and n:
            has_large = True
        if n:
            parts.append(f"{n} {plural_ru(n, forms)}")

    if not has_large and rest:
        parts.append(f"{rest} {plural_ru(rest, ('секунда', 'секунды', 'секунд'))}")

    return " ".join(parts) if parts else "0 секунд"


def format_money(amount: float) -> str:
    """Рубли: 1234567.4 -> «1 234 567 ₽»."""
    return f"{int(round(amount)):,}".replace(",", " ") + " ₽"


def format_distance(ly: float) -> str:
    """Световые годы со склонением единицы: «4.2 св. года», «160 000 св. лет»."""
    if ly >= 1000:
        num = f"{ly:,.0f}".replace(",", " ")
    elif ly >= 1:
        num = f"{ly:.2f}".rstrip("0").rstrip(".")
    elif ly > 0:
        # межпланетные дистанции: фиксированный формат вместо 2.47e-06
        num = f"{ly:.8f}".rstrip("0").rstrip(".") or "0"
    else:
        num = "0"
    if abs(ly - round(ly)) < 1e-9:
        unit = plural_ru(int(round(ly)), ("св. год", "св. года", "св. лет"))
    else:
        unit = "св. года"
    return f"{num} {unit}"


def format_tonnes(value: float) -> str:
    """Тонны: крупные без дроби, мелкие с точностью до граммов."""
    if abs(value) >= 100:
        num = f"{value:,.0f}".replace(",", " ")
    elif abs(value) >= 1:
        num = f"{value:.1f}".rstrip("0").rstrip(".")
    else:
        num = f"{value:.3f}".rstrip("0").rstrip(".") or "0"
    return f"{num} т"
