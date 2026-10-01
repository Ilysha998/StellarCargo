"""Гипердвигатель для межгалактических перелётов (пузырь Алькюбьерре).

Модуль самодостаточный: не импортирует контроллер, не ходит в БД и ничего
не печатает при вызове. Вся конфигурация тира — в этом файле.

Физическая модель (Alcubierre, Phys. Rev. D 50, 1024 (1994); оценки
эффективности — White, Class. Quantum Grav. 28 (2011))
-------------------------------------------------------------------
* корабль НЕ разгоняется локально: пространство внутри пузыря неподвижно,
  поэтому инерции нет, топливо по формуле Циолковского не нужно и груз
  не перегружается ускорением — это отличие от импульсного тира;
* время в пути — чисто координатное: переход идёт со скоростью
  WARP_SPEED_C (метрика Алькюбьерре эффективную скорость пузыря c-ом
  не ограничивает; временное расширение для экипажа отсутствует);
* поддержка пузыря — расход экзотической материи с отрицательной
  энергетической плотностью: пропорционален массе звездолёта и длине
  коридора (чем дальше, тем дольше держать горлышко);
* подъём с планеты — как у всех тиров химической ступенью: топливо
  и время набора высоты растут с гравитацией вылета (требование
  Тимура: g влияет и на топливо, и на время).

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

if __name__ == "__main__":  # автономный запуск из корня: python engines/hyper.py
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

NAME = "Гипер"
MAX_RANGE = 10_000_000.0  # св. лет — Локальная группа (~10 млн св. лет);
                           #  в сиде: Андромеда 2 500 000, Треугольника 2 700 000
WEIGHT_LIMIT = 400.0      # т груза на один корабль — тяжёлый грузовой звездолёт
SHIP_VOLUME_M3 = 20_000.0  # м³ (справочно: флот делит контроллер)

# --- внутренний микроконфиг -------------------------------------------------

WARP_SPEED_C = 1_000_000.0  # кратность световой: метрика Алькюбьерре
                            #  эффективную скорость пузыря не ограничивает;
                            #  10⁶ c -> Андромеда (2,5 млн св. лет) за ~2,5 года
EXOTIC_T_PER_T_PER_LY = 1.0e-7  # т экзотической материи на т массы звездолёта
                                #  на световой год коридора (оценка по White)
LAUNCH_FUEL_FRACTION = 2.5  # доля стартового топлива от полной массы при g = 1
                            #  (химическая ступень подъёма, как у импульсного)
DRY_MASS = 800.0           # т — сухая масса звездолёта (корпус + горлышко)
LOADING_S = 24.0 * 3600.0   # с — погрузка звездолёта перед вылетом
TAKEOFF_S_BASE = 0.5 * 3600.0  # с — набор высоты при g = 1, ×gravity
LAUNCH_FUEL_PRICE_RUB_PER_KG = 100.0   # ₽/кг — химическое стартовое топливо
EXOTIC_PRICE_RUB_PER_KG = 2_000_000.0  # ₽/кг — экзотическая материя (условно)
SHIP_RENT_RUB = 20_000_000.0       # ₽ — аренда звездолёта за рейс
DISTANCE_RATE_RUB_PER_LY = 25_000.0  # ₽/св. год — ставка межгалактического рейса

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
    """Расчёт перелёта на ОДИН корабль гипертира.

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


if __name__ == "__main__":  # демонстрация: межгалактические маршруты
    for label, ly in (
        ("за пределы галактики (как край импульсного)", 300_000.0),
        ("Млечный Путь -> Андромеда", 2_500_000.0),
        ("Млечный Путь -> Треугольника", 2_700_000.0),
    ):
        r = calculate(ly, 300.0, 8_000.0, 1.0)
        print(
            f"{label}, {ly:,.0f} св. лет | топливо {r.fuel_amount:,.1f} т "
            f"({r.fuel_consumption:.4f} т/ч) | время "
            f"{r.flight_time / SECONDS_PER_YEAR:,.1f} лет | "
            f"цена {r.flight_price:,.0f} руб"
        )
