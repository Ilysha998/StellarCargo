"""Реактивный двигатель для перелётов внутри Солнечной системы.

Модуль самодостаточный: не импортирует контроллер, не ходит в БД и ничего
не печатает при вызове. Вся конфигурация тира — в этом файле.

Единицы измерения (единые с контрактом `core.EngineResult`)
-----------------------------------------------------------
    distance          световые годы (как у контроллера)
    cargo_mass        тонны
    cargo_volume      кубометры (м³)
    gravity           g, гравитация планеты вылета (Земля = 1.0)

    fuel_consumption  т/ч   интенсивность расхода (на флот НЕ умножается)
    fuel_amount       т     суммарно на один корабль (взлёт + крейсер)
    flight_price      ₽     за один корабль
    flight_time       с     время в пути (> 0)

Дистанция задаётся в световых годах, но для реактивного двигателя
естественнее астрономические единицы, поэтому она сразу переводится в а.е.
и дальше модель оперирует ими. Внутренние константы расхода оставлены в
литрах и часах (водород, ₽/л), на границе `calculate` переводит топливо
в тонны, а время — в секунды.

Модуль работает в двух режимах:
    * в репозитории StellarCargo — `from core import EngineResult`, тип
      результата общий с контроллером (проверяется через `isinstance`);
    * автономно — если `core` недоступен, используется локальный
      `EngineResult` с теми же полями.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "EngineRangeError",
    "EngineResult",
    "USING_CORE_RESULT",
    "NAME",
    "MAX_RANGE",
    "WEIGHT_LIMIT",
    "SHIP_VOLUME_M3",
    "AU_IN_LY",
    "AU_PER_LY",
    "LITERS_PER_TON",
    "CRUISE_SPEED_AU_PER_S",
    "LAUNCH_RATE_L_PER_G_PER_T",
    "BURN_RATE_L_PER_T_H",
    "LOADING_S",
    "TAKEOFF_S",
    "FUEL_PRICE_RUB_PER_L",
    "SHIP_RENT_RUB",
    "DISTANCE_RATE_RUB_PER_LY",
    "ly_to_au",
    "au_to_ly",
    "fits_range",
    "calculate",
]

# --- публичный контракт тира ------------------------------------------------

NAME = "Реактивный"
MAX_RANGE = 550.0         # св. лет — усреднённый размер звёздной системы
                          # (в сиде средний диаметр системы ≈ 543 св. лет,
                          #  между системами — от 15 000 св. лет)
WEIGHT_LIMIT = 20.0       # т груза на один корабль
SHIP_VOLUME_M3 = 5_000.0     # м³ грузового отсека (справочно: флот делит контроллер)

# --- внутренний микроконфиг -------------------------------------------------

AU_IN_LY = 1.58125e-5     # 1 а.е. в св. годах (та же, что в seed-скрипте)
AU_PER_LY = 1.0 / AU_IN_LY
LITERS_PER_TON = 14_000.0     # л/т — жидкий водород (~0.071 кг/л)
DRY_MASS = 40.0               # т — масса корабля без груза

CRUISE_SPEED_AU_PER_S = 0.001 / 3600.0   # а.е./с — крейсер (0.001 а.е./ч ≈ 149 600 км/ч)
LAUNCH_RATE_L_PER_G_PER_T = 120.0        # л/(g·т) — расход на взлёт
BURN_RATE_L_PER_T_H = 0.4                # л/(т·ч) — расход в крейсерском режиме
LOADING_S = 0.5 * 3600.0                 # с — погрузка на корабль
TAKEOFF_S = 0.3 * 3600.0                 # с — взлёт (постоянная)
FUEL_PRICE_RUB_PER_L = 100.0             # ₽/л — водород
SHIP_RENT_RUB = 15_000.0                 # ₽ — аренда корабля
DISTANCE_RATE_RUB_PER_LY = 250_000.0     # ₽/св.год — ставка за дистанцию

SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86_400.0
LITERS_PER_TON_PER_HOUR = LITERS_PER_TON / SECONDS_PER_HOUR  # т/ч <- л/ч


# --- тип результата: общий с репозиторием или локальный ---------------------


class EngineRangeError(ValueError):
    """Некорректное значение в расчёте или в результате."""


try:  # в репозитории тип результата общий с контроллером
    from core import EngineResult  # type: ignore[attr-defined]

    USING_CORE_RESULT = True
except ImportError:  # автономный режим — тот же контракт, локальный класс
    USING_CORE_RESULT = False

    @dataclass(frozen=True)
    class EngineResult:  # type: ignore[no-redef]
        """Результат расчёта для одного корабля."""

        fuel_consumption: float  # т/ч
        fuel_amount: float       # т
        flight_price: float      # ₽
        flight_time: float       # с

        def validate(self, source: str = NAME) -> "EngineResult":
            """Проверка диапазонов значений. Кидает EngineRangeError."""
            for field in (
                "fuel_consumption",
                "fuel_amount",
                "flight_price",
                "flight_time",
            ):
                value = getattr(self, field)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise EngineRangeError(
                        f"{source}: поле {field} должно быть числом, получено {value!r}"
                    )
                if not math.isfinite(value):
                    raise EngineRangeError(
                        f"{source}: поле {field} должно быть конечным числом, "
                        f"получено {value!r}"
                    )
                if value < 0:
                    raise EngineRangeError(
                        f"{source}: поле {field} не может быть отрицательным ({value!r})"
                    )
            if self.flight_time <= 0:
                raise EngineRangeError(
                    f"{source}: flight_time должен быть больше нуля "
                    f"(получено {self.flight_time!r})"
                )
            return self


# --- перевод единиц ---------------------------------------------------------


def ly_to_au(distance_ly: float) -> float:
    """Световые годы → астрономические единицы."""
    return distance_ly * AU_PER_LY


def au_to_ly(distance_au: float) -> float:
    """Астрономические единицы → световые годы."""
    return distance_au * AU_IN_LY


def fits_range(distance_ly: float) -> bool:
    """Покрывает ли двигатель дистанцию (св. лет).

    Выбор тира по дальности делает контроллер — `calculate` этот лимит
    не проверяет, хелпер нужен для отладки и тестов.
    """
    return distance_ly <= MAX_RANGE


# --- расчёт -----------------------------------------------------------------


def _check_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} должно быть числом, получено {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} должно быть конечным числом, получено {value!r}")
    if value < 0:
        raise ValueError(f"{name} не может быть отрицательным ({value!r})")
    return value


def calculate(
    distance: float,
    cargo_mass: float,
    cargo_volume: float,
    gravity: float,
) -> EngineResult:
    """Расчёт перелёта на ОДИН корабль реактивного двигателя.

    distance     — дистанция, световые годы
    cargo_mass   — масса груза, тонны
    cargo_volume — объём груза, м³
    gravity      — гравитация планеты вылета, g (> 0)

    Лимиты `WEIGHT_LIMIT`, `SHIP_VOLUME_M3` и `MAX_RANGE` намеренно не
    проверяются: груз делится между кораблями и тир выбирается
    контроллером до вызова движка.
    """
    distance = _check_number("distance", distance)
    cargo_mass = _check_number("cargo_mass", cargo_mass)
    _check_number("cargo_volume", cargo_volume)
    gravity = _check_number("gravity", gravity)

    if gravity == 0:
        raise ValueError("gravity должен быть больше нуля")

    distance_au = ly_to_au(distance)
    mass_total = cargo_mass + DRY_MASS

    fuel_launch_l = LAUNCH_RATE_L_PER_G_PER_T * gravity * mass_total
    cruise_s = distance_au / CRUISE_SPEED_AU_PER_S
    fuel_cruise_l = mass_total * BURN_RATE_L_PER_T_H * cruise_s / SECONDS_PER_HOUR
    fuel_l = fuel_launch_l + fuel_cruise_l

    fuel_t = fuel_l / LITERS_PER_TON
    fuel_consumption = fuel_l / max(cruise_s / SECONDS_PER_HOUR, 1.0) / LITERS_PER_TON

    flight_price = (
        fuel_l * FUEL_PRICE_RUB_PER_L
        + SHIP_RENT_RUB
        + DISTANCE_RATE_RUB_PER_LY * distance
    )
    flight_time = LOADING_S + TAKEOFF_S + cruise_s

    return EngineResult(
        fuel_consumption=fuel_consumption,
        fuel_amount=fuel_t,
        flight_price=flight_price,
        flight_time=flight_time,
    ).validate(NAME)


if __name__ == "__main__":  # демонстрация: Земля -> Марс, Земля -> Нептун
    for label, ly in (
        ("Земля -> Марс", 0.52 * AU_IN_LY),
        ("Земля -> Нептун", 29.05 * AU_IN_LY),
    ):
        r = calculate(ly, 20.0, SHIP_VOLUME_M3, 1.0)
        print(
            f"{label}: {ly:.3e} св. лет | топливо {r.fuel_amount:,.3f} т "
            f"({r.fuel_consumption:.4f} т/ч) | время {r.flight_time:,.0f} с "
            f"({r.flight_time / SECONDS_PER_DAY:,.1f} сут) | цена {r.flight_price:,.0f} руб"
        )
