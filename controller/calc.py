"""Расчёт маршрута: связка базы планет, выбора двигателя и флота.

Константы флота контроллера живут здесь же (решение: отдельного
файла конфига в проекте нет).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import FleetTooLargeError, StellarCargoError
from . import db, engines as engine_hub, geometry
from .db import Planet

# --- конфиг контроллера (в отдельный файл выносить нельзя) -----------------
SHIP_VOLUME = 5_000.0   # м³ грузового отсека одного корабля
MAX_FLEET = 20          # максимум кораблей во флоте
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlightResult:
    """Всё, что уходит вызывающему (main-функция)."""

    selected_engine: str   # имя тира из переменной контроллера
    fuel_consumption: float  # т/ч на корабль
    fuel_amount: float     # т суммарно по флоту (пуск + крейсер)
    flight_price: float    # ₽ суммарно по флоту
    flight_time: float     # с (для всего флота одинаково)
    ships: int             # кораблей во флоте
    distance: float        # св. лет
    origin: Planet
    destination: Planet


def ships_needed(
    cargo_mass: float,
    cargo_volume: float,
    weight_limit: float,
    ship_volume: float = SHIP_VOLUME,
    max_fleet: int = MAX_FLEET,
) -> int:
    """Сколько кораблей нужно: по весу (лимит движка) и по объёму (корабль)."""
    by_mass = cargo_mass / weight_limit if cargo_mass > 0 else 0.0
    by_volume = cargo_volume / ship_volume if cargo_volume > 0 else 0.0
    ships = math.ceil(max(by_mass, by_volume))
    ships = max(1, ships)
    if ships > max_fleet:
        need_mass = math.ceil(by_mass)
        need_volume = math.ceil(by_volume)
        raise FleetTooLargeError(
            f"Груз не помещается во флот: нужно {ships} кораблей "
            f"(по весу {need_mass}, по объёму {need_volume}), максимум {max_fleet}. "
            f"Разделите груз или уменьшите его."
        )
    return ships


def main(
    planet_from: str,
    planet_destination: str,
    cargo_volume: float,
    cargo_mass: float,
) -> FlightResult:
    """Расчёт перелёта. Возвращает все переменные вызывающему.

    Вход: две планеты (id или название), объём и масса груза (на весь флот).
    Движок выбирается контроллером только по дальности маршрута.
    """
    origin = db.get_planet(planet_from)
    destination = db.get_planet(planet_destination)

    for label, value in (("cargo_volume", cargo_volume), ("cargo_mass", cargo_mass)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise StellarCargoError(f"{label} должен быть числом, получено {value!r}")
        if not math.isfinite(value) or value < 0:
            raise StellarCargoError(f"{label} должен быть неотрицательным и конечным.")
    if cargo_volume == 0 and cargo_mass == 0:
        raise StellarCargoError("Груз не задан: укажите массу и/или объём.")

    distance = geometry.distance(origin, destination)

    engine = engine_hub.select_engine(distance)
    ships = ships_needed(cargo_mass, cargo_volume, engine.WEIGHT_LIMIT)

    # Делим груз между кораблями — движок считает по одному кораблю.
    mass_per_ship = cargo_mass / ships
    volume_per_ship = cargo_volume / ships

    result = engine_hub.call_engine(
        engine, distance, mass_per_ship, volume_per_ship, origin.gravity
    )

    return FlightResult(
        selected_engine=engine.NAME,
        fuel_consumption=result.fuel_consumption,
        fuel_amount=result.fuel_amount * ships,   # топливо — на весь флот
        flight_price=result.flight_price * ships, # цена — на весь флот
        flight_time=result.flight_time,           # время — как у одного корабля
        ships=ships,
        distance=distance,
        origin=origin,
        destination=destination,
    )
