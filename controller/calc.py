"""Расчёт маршрута: связка базы планет, выбора двигателя и флота.

Константы флота контроллера живут здесь же (решение: отдельного
файла конфига в проекте нет).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import PlanetNotFoundError, StellarCargoError
from . import db, engines as engine_hub, geometry
from .db import Planet

# --- конфиг контроллера (в отдельный файл выносить нельзя) -----------------
SHIP_VOLUME = 5_000.0   # м³ грузового отсека одного корабля
MAX_FLEET = 20          # максимум кораблей в одном вылете (ходке)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlightResult:
    """Всё, что уходит вызывающему (main-функция)."""

    selected_engine: str   # имя тира из переменной контроллера
    fuel_consumption: float  # т/ч на корабль
    fuel_amount: float     # т суммарно по всем ходкам (пуск + крейсер)
    flight_price: float    # ₽ суммарно по всем ходкам
    flight_time: float     # с (волны уходят с интервалом погрузки, в полёте параллельно)
    ships: int             # кораблей в одном вылете
    trips: int             # ходок (вылетов) по ships кораблей
    distance: float        # св. лет
    origin: Planet
    destination: Planet


def ships_needed(
    cargo_mass: float,
    cargo_volume: float,
    weight_limit: float,
    ship_volume: float = SHIP_VOLUME,
) -> int:
    """Сколько кораблей-загрузок нужно на весь груз: по весу и по объёму."""
    by_mass = cargo_mass / weight_limit if cargo_mass > 0 else 0.0
    by_volume = cargo_volume / ship_volume if cargo_volume > 0 else 0.0
    return max(1, math.ceil(max(by_mass, by_volume)))


def fleet_plan(
    needed: int, max_fleet: int = MAX_FLEET
) -> tuple[int, int]:
    """План флота: (кораблей в вылете, ходок).

    Груз, который не влезает в один вылет (max_fleet), делится на ходки:
    needed=25 -> (20 кораблей, 2 ходки).
    """
    needed = max(1, needed)
    trips = math.ceil(needed / max_fleet)
    ships = min(needed, max_fleet)
    return ships, trips


def main(
    planet_from: str,
    planet_destination: str,
    cargo_volume: float,
    cargo_mass: float,
) -> FlightResult:
    """Расчёт перелёта. Возвращает все переменные вызывающему.

    Вход: две планеты (id или название), объём и масса груза (на весь груз).
    Движок выбирается контроллером только по дальности маршрута.
    Если груз не влезает в один вылет (MAX_FLEET кораблей) — считаются
    ходки: топливо и цена ×число ходок; волны вылетают одна за другой
    с интервалом погрузки (LOADING_S движка), в полёте летят параллельно,
    поэтому время = базовое время движка + (ходки − 1) × погрузка.
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
    needed = ships_needed(cargo_mass, cargo_volume, engine.WEIGHT_LIMIT)
    ships, trips = fleet_plan(needed)
    slots = ships * trips  # всего корабле-вылетов

    # Делим груз равномерно по всем ходкам — движок считает по одному кораблю.
    mass_per_ship = cargo_mass / slots
    volume_per_ship = cargo_volume / slots

    result = engine_hub.call_engine(
        engine, distance, mass_per_ship, volume_per_ship, origin.gravity
    )

    # Волны: следующая вылетает после погрузки предыдущей (интервал —
    # LOADING_S движка; если движок атрибут не публикует — интервала нет).
    # В полёте волны параллельны, поэтому сам перелёт не удлиняется.
    loading_s = float(getattr(engine, "LOADING_S", 0.0))
    wave_lag_s = (trips - 1) * max(loading_s, 0.0)

    return FlightResult(
        selected_engine=engine.NAME,
        fuel_consumption=result.fuel_consumption,
        fuel_amount=result.fuel_amount * slots,   # топливо — все ходки
        flight_price=result.flight_price * slots, # цена — все ходки
        flight_time=result.flight_time + wave_lag_s,  # база + интервалы волн
        ships=ships,
        trips=trips,
        distance=distance,
        origin=origin,
        destination=destination,
    )
