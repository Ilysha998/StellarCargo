"""Импульсный двигатель для межзвёздных перелётов внутри галактики.

Модуль самодостаточный: не импортирует контроллер, не ходит в БД и ничего
не печатает при вызове. Вся конфигурация тира — в этом файле.

Физическая модель (термоядерный привод класса Daedalus / Icarus)
-----------------------------------------------------------------
* крейсерская скорость 0.05 c — проект Icarus довозит 4,37 св. года
  за 100 лет (≈ 0.044 c), взято округлённо 5% световой;
* удельный импульс 10⁶ с (скорость истечения ≈ 9 810 км/с ≈ 0.033 c) —
  уровень инерциального термоядерного двигателя проекта Daedalus (D-He3);
* топливо маршрута считается по формуле Циолковского на две фазы —
  разгон до крейсерской скорости и торможение перед целью
  (Δv = 2 × v_крейсер). На крейсерском участке корабль идёт по инерции,
  расхода нет, поэтому fuel_amount от дистанции НЕ зависит — только
  от массы и гравитации вылета;
* фазы разгона/торможения идут с ускорением ACCEL_MS (~0.0001 g —
  порядок импульсной/ионной тяги) и включены во flight_time;
* подъём с планеты — отдельной тепловой ступенью (Isp ≈ 900 с):
  доля стартового топлива и время набора высоты растут с гравитацией
  планеты вылета (требование Тимура: g влияет и на топливо, и на время).

Единицы измерения (единые с контрактом `core.EngineResult`)
-----------------------------------------------------------
    distance          световые годы (как у контроллера)
    cargo_mass        тонны
    cargo_volume      кубометры (м³)
    gravity           g, гравитация планеты вылета (Земля = 1.0)

    fuel_consumption  т/ч   интенсивность в активных фазах (только подъём
                            + разгон/торможение; крейсер без расхода)
    fuel_amount       т     суммарно на один корабль (подъём + разгон + торможение)
    flight_price      ₽     за один корабль
    flight_time       с     погрузка + подъём + разгон + крейсер + торможение
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
    "CRUISE_SPEED_C",
    "I_SP_S",
    "EXHAUST_SPEED_MS",
    "ACCEL_MS",
    "DRY_MASS",
    "LAUNCH_FUEL_FRACTION",
    "LOADING_S",
    "TAKEOFF_S_BASE",
    "FUEL_PRICE_RUB_PER_KG",
    "SHIP_RENT_RUB",
    "DISTANCE_RATE_RUB_PER_LY",
    "LY_KM",
    "C_M_S",
    "SECONDS_PER_HOUR",
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

CRUISE_SPEED_C = 0.05            # крейсер 5% световой (Icarus: 4,37 св. года / 100 лет)
I_SP_S = 1_000_000.0             # с — удельный импульс, термоядерный привод (Daedalus)
G0 = 9.80665                     # м/с² — стандартное свободное падение
EXHAUST_SPEED_MS = I_SP_S * G0   # ≈ 9 810 км/с ≈ 0.033 c
ACCEL_MS = 1.0e-3                # м/с² — среднее ускорение фаз разгона/торможения
DRY_MASS = 300.0                 # т — сухая масса фрейхтера (корабль + экипаж)
LAUNCH_FUEL_FRACTION = 2.5       # доля стартового топлива от полной массы при g = 1
                                 #  (тепловая ступень, Isp 900 с, Δv ≈ 10,8 км/с:
                                 #   exp(10800 / (900 * G0)) - 1 ≈ 2.5)
LOADING_S = 12.0 * 3600.0        # с — погрузка фрейхтера перед вылетом
TAKEOFF_S_BASE = 0.5 * 3600.0    # с — набор высоты при g = 1, ×gravity
FUEL_PRICE_RUB_PER_KG = 1_500.0  # ₽/кг — топливные пеллеты D-He3 (условно)
SHIP_RENT_RUB = 5_000_000.0      # ₽ — аренда фрейхтера за рейс
DISTANCE_RATE_RUB_PER_LY = 100_000.0  # ₽/св. год — ставка межзвёздного рейса

LY_KM = 9.4607304725808e12       # км в одном световом году
C_M_S = 299_792_458.0            # м/с — скорость света
SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86_400.0
SECONDS_PER_YEAR = 365.0 * SECONDS_PER_DAY

# производные величины (считаются один раз при импорте)
_CRUISE_SPEED_MS = CRUISE_SPEED_C * C_M_S
_DELTA_V_MS = 2.0 * _CRUISE_SPEED_MS          # разгон + торможение
_BURN_FUEL_RATIO = math.exp(_DELTA_V_MS / EXHAUST_SPEED_MS) - 1.0  # ~20.3
_BURN_S = _DELTA_V_MS / ACCEL_MS              # суммарное время активных фаз ~950 лет


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

    # топливо: подъём из гравитационной ямы (∝ g) + две фазы по Циолковскому
    fuel_launch_t = LAUNCH_FUEL_FRACTION * gravity * mass_total
    fuel_burn_t = _BURN_FUEL_RATIO * mass_total
    fuel_t = fuel_launch_t + fuel_burn_t

    # время: погрузка + подъём (∝ g) + разгон/торможение + крейсер
    distance_km = distance * LY_KM
    cruise_s = distance_km * 1000.0 / _CRUISE_SPEED_MS
    takeoff_s = TAKEOFF_S_BASE * gravity
    active_s = takeoff_s + _BURN_S  # фазы с расходом топлива
    flight_time = LOADING_S + active_s + cruise_s

    fuel_consumption = fuel_t / (active_s / SECONDS_PER_HOUR)

    flight_price = (
        fuel_t * 1000.0 * FUEL_PRICE_RUB_PER_KG
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
            f"{r.flight_time / SECONDS_PER_YEAR:,.0f} лет | "
            f"цена {r.flight_price:,.0f} руб"
        )
