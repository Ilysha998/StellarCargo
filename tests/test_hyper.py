"""Тесты гипертира: контракт, физика пузыря, гравитация (Тимур)."""

import pytest

from core import EngineResult
from controller import engines as engine_hub
from engines import hyper


def test_contract_attrs():
    assert isinstance(hyper.NAME, str) and hyper.NAME.strip()
    assert hyper.MAX_RANGE > 0
    assert hyper.WEIGHT_LIMIT > 0
    engine_hub.validate_engine(hyper)
    # должен закрывать самые дальние маршруты сида
    # (Андромеда/Треугольника ~2 700 000 св. лет)
    assert hyper.MAX_RANGE >= 2_700_000.0


def test_tier_order_by_range():
    """Лестница тиров: ракетный < импульсный < гипер."""
    from engines import impulse, rocket

    assert rocket.MAX_RANGE < impulse.MAX_RANGE < hyper.MAX_RANGE


def test_result_is_core_engine_result():
    r = hyper.calculate(2_500_000.0, 300.0, 8_000.0, 1.0)
    assert isinstance(r, EngineResult)
    r.validate("Гипер")


def test_no_tsiolkovsky_fuel_explosion():
    """Пузырь не разгоняется локально: топливо почти не зависит от дистанции
    (только лёгкий рост коридора), в отличие от Циолковского у импульсного."""
    near = hyper.calculate(300_000.0, 300.0, 8_000.0, 1.0)
    far = hyper.calculate(2_700_000.0, 300.0, 8_000.0, 1.0)
    assert far.fuel_amount > near.fuel_amount
    # рост пропорционален дистанции и мал: < 2x при росте дистанции в 9 раз
    assert far.fuel_amount < near.fuel_amount * 2.0
    assert far.flight_time > near.flight_time
    assert far.flight_price > near.flight_price


def test_andromeda_in_about_two_and_half_years():
    r = hyper.calculate(2_500_000.0, 300.0, 8_000.0, 1.0)
    years = r.flight_time / hyper.SECONDS_PER_YEAR
    assert 2.4 < years < 2.7  # 10^6 c + сутки погрузки + подъём


def test_gravity_raises_fuel_and_time():
    low = hyper.calculate(2_500_000.0, 300.0, 8_000.0, 0.38)
    high = hyper.calculate(2_500_000.0, 300.0, 8_000.0, 1.0)
    assert high.fuel_amount > low.fuel_amount
    assert high.flight_time > low.flight_time


def test_heavier_cargo_costs_more():
    light = hyper.calculate(2_500_000.0, 100.0, 8_000.0, 1.0)
    heavy = hyper.calculate(2_500_000.0, 390.0, 8_000.0, 1.0)
    assert heavy.fuel_amount > light.fuel_amount
    assert heavy.flight_price > light.flight_price


def test_range_helper():
    assert hyper.fits_range(9_999_999.0)
    assert not hyper.fits_range(10_000_001.0)


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_rejects_bad_distance(bad):
    with pytest.raises(ValueError):
        hyper.calculate(bad, 300.0, 8_000.0, 1.0)


def test_rejects_zero_gravity():
    with pytest.raises(ValueError):
        hyper.calculate(2_500_000.0, 300.0, 8_000.0, 0.0)


def test_controller_picks_hyper_for_intergalactic_route(planets_db):
    """Маршрут до Андромеды дальше всех тиров, кроме гипера."""
    from controller import calc

    res = calc.main("MW-SLR-EARTH", "AND-KAP-DAWN", 100, 50)
    assert res.selected_engine == "Гипер"
    assert res.distance > 2_000_000.0
    assert res.flight_time > 0
