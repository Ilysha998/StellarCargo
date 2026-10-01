"""Тесты импульсного тира: контракт, физика, гравитация (Тимур)."""

import math

import pytest

from core import EngineResult
from controller import engines as engine_hub
from engines import impulse


def test_contract_attrs():
    assert isinstance(impulse.NAME, str) and impulse.NAME.strip()
    assert impulse.MAX_RANGE > 0
    assert impulse.WEIGHT_LIMIT > 0
    engine_hub.validate_engine(impulse)
    # тир обязан закрывать внутригалактические маршруты сида (диаметр
    # Андромеды в seed = 160 000 св. лет)
    assert impulse.MAX_RANGE >= 160_000.0


def test_result_is_core_engine_result():
    r = impulse.calculate(15_000.0, 100.0, 4_000.0, 1.0)
    assert isinstance(r, EngineResult)
    r.validate("Импульсный")


def test_fuel_independent_of_distance():
    """Крейсер идёт по инерции: топливо зависит от массы, не от дистанции."""
    near = impulse.calculate(600.0, 100.0, 4_000.0, 1.0)
    far = impulse.calculate(100_000.0, 100.0, 4_000.0, 1.0)
    assert near.fuel_amount == pytest.approx(far.fuel_amount)
    assert far.flight_time > near.flight_time
    assert far.flight_price > near.flight_price


def test_gravity_raises_fuel_and_time():
    low = impulse.calculate(15_000.0, 100.0, 4_000.0, 0.38)
    high = impulse.calculate(15_000.0, 100.0, 4_000.0, 1.0)
    assert high.fuel_amount > low.fuel_amount
    assert high.flight_time > low.flight_time


def test_heavier_cargo_costs_more():
    light = impulse.calculate(15_000.0, 50.0, 4_000.0, 1.0)
    heavy = impulse.calculate(15_000.0, 110.0, 4_000.0, 1.0)
    assert heavy.fuel_amount > light.fuel_amount
    assert heavy.flight_price > light.flight_price


def test_time_is_years_not_days():
    """0.05c: 15 000 св. лет — сотни тысяч лет (кросс-чек по формуле)."""
    r = impulse.calculate(15_000.0, 100.0, 4_000.0, 1.0)
    ly_per_s = 0.05 * 299_792_458.0 / (impulse.LY_KM * 1000.0)
    cruise = 15_000.0 / ly_per_s
    assert r.flight_time > cruise
    assert r.flight_time < cruise * 1.02 + impulse.LOADING_S


def test_range_helper():
    assert impulse.fits_range(199_999.0)
    assert not impulse.fits_range(200_001.0)


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_rejects_bad_distance(bad):
    with pytest.raises(ValueError):
        impulse.calculate(bad, 100.0, 4_000.0, 1.0)


def test_rejects_zero_gravity():
    with pytest.raises(ValueError):
        impulse.calculate(15_000.0, 100.0, 4_000.0, 0.0)


def test_controller_picks_impulse_for_galaxy_route(monkeypatch, planets_db):
    """Маршрут внутри галактики: ракетный не тянет (MAX_RANGE 550)."""
    from controller import calc

    res = calc.main("MW-SLR-EARTH", "MW-ALF-NOVA", 100, 50)
    assert res.selected_engine == "Импульсный"
    assert res.distance > 550.0
    assert res.flight_time > 0
    assert not math.isnan(res.flight_price)
