"""Контракт между контроллером и модулями двигателей.

Это единственная точка, которую импортируют и контроллер, и модули
участников (Rocket / Impulse / Hyper). Здесь нет логики — только
тип результата и ошибки.

Единицы измерения по контракту:
    distance       световые годы
    cargo_mass     тонны
    cargo_volume   кубометры (м³)
    gravity        ускорение свободного падения планеты вылета (g, Земля = 1.0)
    fuel_consumption  тонн в час (интенсивность, на флот НЕ умножается)
    fuel_amount    тонны (суммарно на один корабль: пуск + крейсер)
    flight_price   рубли (за один корабль)
    flight_time    секунды (> 0)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "EngineResult",
    "StellarCargoError",
    "EngineContractError",
    "EngineSelectionError",
    "FleetTooLargeError",
    "PlanetNotFoundError",
]


@dataclass(frozen=True)
class EngineResult:
    """Результат calculate() одного двигателя на ОДИН корабль."""

    fuel_consumption: float  # т/ч, интенсивность (не умножается на кол-во кораблей)
    fuel_amount: float       # т, суммарно на корабль (пуск от гравитации + крейсер)
    flight_price: float      # ₽ за корабль
    flight_time: float       # с, время в пути (одинаково для всего флота)

    def validate(self, source: str = "двигатель") -> "EngineResult":
        """Проверка диапазонов значений. Кидает EngineContractError."""
        for field in (
            "fuel_consumption",
            "fuel_amount",
            "flight_price",
            "flight_time",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EngineContractError(
                    f"{source}: поле {field} должно быть числом, получено {value!r}"
                )
            if not math.isfinite(value):
                raise EngineContractError(
                    f"{source}: поле {field} должно быть конечным числом, получено {value!r}"
                )
            if value < 0:
                raise EngineContractError(
                    f"{source}: поле {field} не может быть отрицательным ({value!r})"
                )
        if self.flight_time <= 0:
            raise EngineContractError(
                f"{source}: flight_time должен быть больше нуля (получено {self.flight_time!r})"
            )
        return self


class StellarCargoError(Exception):
    """Базовая ошибка проекта — её ловит TUI и показывает пользователю."""


class EngineContractError(StellarCargoError):
    """Двигатель не соответствует контракту (атрибуты, типы, calculate)."""


class EngineSelectionError(StellarCargoError):
    """Нет пригодного двигателя под дистанцию маршрута."""


class FleetTooLargeError(StellarCargoError):
    """Груз не помещается в допустимое количество кораблей."""


class PlanetNotFoundError(StellarCargoError):
    """Планета не найдена в базе (или название неоднозначно)."""
