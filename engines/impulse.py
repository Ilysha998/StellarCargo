"""Импульсный двигатель для межзвёздных перелётов внутри галактики (варп).

Модуль самодостаточный: не импортирует контроллер, не ходит в БД и ничего
не печатает при вызове. Вся конфигурация тира — в этом файле.

Физическая модель (варп-привод, упрощённая метрика Алькюбьерре)
-------------------------------------------------------------------
* корабль не разгоняется локально: пространство внутри пузыря неподвижно,
  инерции нет, топливо по Циолковскому не нужно — как у гипертира;
* время в пути — чисто координатное: переход идёт со скоростью
  WARP_SPEED_C (2000 c — в 500 раз медленнее гипера, поэтому дальние
  внутригалактические маршруты занимают годы и десятилетия, а не сутки);
* поддержка пузыря — расход экзотической материи: пропорционален массе
  фрейхтера и длине коридора;
* подъём с планеты — химической ступенью: топливо и время набора
  высоты растут с гравитацией вылета (требование Тимура: g влияет
  и на топливо, и на время).

Единицы измерения (единые с контрактом `core.EngineResult`)
-----------------------------------------------------------
     distance          световые годы (как у контроллера)
     cargo_mass        тонны
     cargo_volume      кубометры (м³)
     gravity           g, гравитация планеты вылета (Земля = 1.0)

     fuel_consumption  т/ч   интенсивность расхода (подъём + коридор)
     fuel_amount       т     суммарно на один корабль (подъём + экзотика)
     flight_price      ₽     за один корабль
     flight_time       с     погрузка + подъём + переход по коридору
"""

from __future__ import annotations

import math

if __name__ == "__main__":  # автономный запуск из корня: python engines/impulse.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import EngineResult

__all__ = [
    "NAME",
    "MAX_RANGE",
    "WEIGHT_LIMIT",
    "SHIP_VOLUME_M3",
    "WARP_SPEED_C",
    "EXOTIC_T_PER_T_PER_LY",
    "DRY_MASS",
    "LAUNCH_FUEL_FRACTION",
    "LOADING_S",
    "TAKEOFF_S_BASE",
    "LAUNCH_FUEL_PRICE_RUB_PER_KG",
    "EXOTIC_PRICE_RUB_PER_KG",
    "SHIP_RENT_RUB",
    "DISTANCE_RATE_RUB_PER_LY",
    "LY_KM",
    "C_M_S",
    "SECONDS_PER_HOUR",
    "SECONDS_PER_YEAR",
    "fits_range",
    "calculate",
]

# --- публичный контракт тира ------------------------------------------------

NAME = "Импульсный"
MAX_RANGE = 200_000.0    # св. лет — внутри галактики (в сиде: MW 100 000,
                         #  Андромеда 160 000 в поперечнике)
WEIGHT_LIMIT = 120.0     # т груза на один корабль — фрейхтер тяжелее ракетного
SHIP_VOLUME_M3 = 5_000.0  # м³ (справочно: флот делит контроллер)

# --- внутренний микроконфиг -------------------------------------------------

WARP_SPEED_C = 2_500.0  # кратность световой: варп-пузырь слабее гиперного
                        #  (10⁶ c) в 400 раз -> 200 000 св. лет за ~80 лет
EXOTIC_T_PER_T_PER_LY = 1.0e-7  # т экзотической материи на т массы фрейхтера
                                #  на световой год коридора (оценка по White)
LAUNCH_FUEL_FRACTION = 2.5  # доля стартового топлива от полной массы при g = 1
                            #  (химическая ступень подъёма, как у гиперного)
DRY_MASS = 300.0           # т — сухая масса фрейхтера (корабль + экипаж)
LOADING_S = 12.0 * 3600.0   # с — погрузка фрейхтера перед вылетом
TAKEOFF_S_BASE = 0.5 * 3600.0  # с — набор высоты при g = 1, ×gravity
LAUNCH_FUEL_PRICE_RUB_PER_KG = 100.0   # ₽/кг — химическое стартовое топливо
EXOTIC_PRICE_RUB_PER_KG = 2_000_000.0  # ₽/кг — экзотическая материя (условно)
SHIP_RENT_RUB = 5_000_000.0       # ₽ — аренда фрейхтера за рейс
DISTANCE_RATE_RUB_PER_LY = 100_000.0  # ₽/св. год — ставка межзвёздного рейса

LY_KM = 9.4607304725808e12  # км в одном световом году
C_M_S = 299_792_458.0       # м/с — скорость света
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86_400.0
SECONDS_PER_YEAR = 365.0 * SECONDS_PER_DAY


# --- диапазон ---------------------------------------------------------------


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
    """Расчёт перелёта на ОДИН корабль импульсного тира.

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

    mass_total = cargo_mass + DRY_MASS

    # топливо: химический подъём (∝ g) + экзотика на держание коридора
    fuel_launch_t = LAUNCH_FUEL_FRACTION * gravity * mass_total
    fuel_exotic_t = EXOTIC_T_PER_T_PER_LY * mass_total * distance
    fuel_t = fuel_launch_t + fuel_exotic_t

    # время: погрузка + подъём (∝ g) + чисто координатный переход
    distance_km = distance * LY_KM
    warp_s = distance_km * 1000.0 / (WARP_SPEED_C * C_M_S)
    takeoff_s = TAKEOFF_S_BASE * gravity
    flight_time = LOADING_S + takeoff_s + warp_s

    active_s = takeoff_s + warp_s  # фазы с расходом (для интенсивности)
    fuel_consumption = fuel_t / max(active_s / SECONDS_PER_HOUR, 1.0)

    # цена складывается из двух топлив по разным ценам
    flight_price = (
        fuel_launch_t * 1000.0 * LAUNCH_FUEL_PRICE_RUB_PER_KG
        + fuel_exotic_t * 1000.0 * EXOTIC_PRICE_RUB_PER_KG
        + SHIP_RENT_RUB
        + DISTANCE_RATE_RUB_PER_LY * distance
    )

    return EngineResult(
        fuel_consumption=fuel_consumption,
        fuel_amount=fuel_t,
        flight_price=flight_price,
        flight_time=flight_time,
    ).validate(NAME)


if __name__ == "__main__":  # демонстрация: межсистемные и межгалактические маршруты
    for label, ly in (
        ("соседняя система (как у ракетного на максимуме)", 600.0),
        ("межсистемный переход", 15_000.0),
        ("поперёк галактики", 100_000.0),
    ):
        r = calculate(ly, 100.0, 4_000.0, 1.0)
        print(
            f"{label}, {ly:,.0f} св. лет | топливо {r.fuel_amount:,.1f} т "
            f"({r.fuel_consumption:.4f} т/ч) | время "
            f"{r.flight_time / SECONDS_PER_YEAR:,.1f} лет | "
            f"цена {r.flight_price:,.0f} руб"
        )
