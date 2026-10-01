"""Загрузка модулей двигателей и выбор по дальности.

Контроллер не знает о движках ничего, кроме их публичных атрибутов:
    NAME          str    — человекочитаемое имя тира («Ракетный»)
    MAX_RANGE     float  — максимальная дальность, световые годы
    WEIGHT_LIMIT  float  — максимум груза на один корабль, тонн
    calculate(distance, cargo_mass, cargo_volume, gravity) -> EngineResult
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Iterable

from core import EngineContractError, EngineResult, EngineSelectionError

# Порядок = порядок проверки: сначала дальний-на-дальность охват.
ENGINE_MODULE_PATHS: tuple[str, ...] = (
    "engines.rocket",
    "engines.impulse",
    "engines.hyper",
)

_REQUIRED_ATTRS = ("NAME", "MAX_RANGE", "WEIGHT_LIMIT", "calculate")


def validate_engine(module: ModuleType) -> None:
    """Проверка контракта модуля двигателя. Кидает EngineContractError."""
    for attr in _REQUIRED_ATTRS:
        if not hasattr(module, attr):
            raise EngineContractError(
                f"Модуль {module.__name__} не соответствует контракту: "
                f"нет атрибута {attr!r}. См. docs/CONTRACT.md"
            )
    if not isinstance(module.NAME, str) or not module.NAME.strip():
        raise EngineContractError(f"{module.__name__}: NAME должен быть непустой строкой.")
    for attr in ("MAX_RANGE", "WEIGHT_LIMIT"):
        value = getattr(module, attr)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise EngineContractError(
                f"{module.__name__}: {attr} должен быть положительным числом, получено {value!r}"
            )
    if not callable(module.calculate):
        raise EngineContractError(f"{module.__name__}: calculate должен быть функцией.")


def load_engines(paths: Iterable[str] | None = None) -> list[ModuleType]:
    """Импортирует и валидирует все доступные модули двигателей.

    Нехватка какого-то модуля не фатальна — контроллер работает
    с тем, что есть. Некорректный (есть, но кривой) — EngineContractError.
    """
    engines: list[ModuleType] = []
    for path in paths if paths is not None else ENGINE_MODULE_PATHS:
        try:
            module = importlib.import_module(path)
        except ImportError:
            continue  # участник ещё не положил свой модуль
        validate_engine(module)
        engines.append(module)
    return engines


def select_engine(
    distance: float, engines: list[ModuleType] | None = None
) -> ModuleType:
    """Первый двигатель, чей MAX_RANGE покрывает дистанцию.

    Список сортируется по MAX_RANGE: ракетный -> импульсный -> гипер.
    """
    if engines is None:
        engines = load_engines()
    if not engines:
        raise EngineSelectionError(
            "Ни один модуль двигателя не найден. Проверьте пакет engines/ "
            "и что ветки Rocket/Impulse/Hyper смержены."
        )
    for module in sorted(engines, key=lambda m: m.MAX_RANGE):
        if distance <= module.MAX_RANGE:
            return module
    best = max(m.MAX_RANGE for m in engines)
    raise EngineSelectionError(
        f"Маршрут длиннее доступной дальности: {distance:g} св. лет "
        f"(максимум {best:g} св. лет)."
    )


def call_engine(
    engine: ModuleType,
    distance: float,
    cargo_mass: float,
    cargo_volume: float,
    gravity: float,
) -> EngineResult:
    """Вызов calculate с валидацией результата. Кидает EngineContractError."""
    try:
        result = engine.calculate(distance, cargo_mass, cargo_volume, gravity)
    except EngineContractError:
        raise
    except Exception as exc:  # движок упал на своих данных — это его ошибка
        raise EngineContractError(
            f"{engine.NAME}: calculate() завершился ошибкой: {exc}"
        ) from exc
    if not isinstance(result, EngineResult):
        raise EngineContractError(
            f"{engine.NAME}: calculate() должен возвращать EngineResult, "
            f"получено {type(result).__name__}."
        )
    return result.validate(source=engine.NAME)
