import pytest

from controller import calc, engines as engine_hub, formatting


def test_format_duration():
    assert formatting.format_duration(0) == "0 секунд"
    assert formatting.format_duration(45) == "45 секунд"
    assert formatting.format_duration(3600) == "1 час"
    day = 365 * 86400 * 10 + 30 * 86400 * 2 + 3 * 86400
    assert formatting.format_duration(day) == "10 лет 2 месяца 3 дня"
    assert formatting.format_duration(11 * 86400) == "11 дней"


def test_format_money_and_tonnes():
    assert formatting.format_money(1_234_567.4) == "1 234 567 ₽"
    assert formatting.format_tonnes(1234.6) == "1 235 т"
    assert formatting.format_tonnes(0.5) == "0.5 т"


def test_format_distance():
    assert formatting.format_distance(1) == "1 св. год"
    assert formatting.format_distance(2) == "2 св. года"
    assert formatting.format_distance(5) == "5 св. лет"
    assert formatting.format_distance(4.20) == "4.2 св. года"
    assert formatting.format_distance(2.47e-6) == "0.00000247 св. года"


def test_plural_ru():
    assert formatting.plural_ru(1, ("год", "года", "лет")) == "год"
    assert formatting.plural_ru(2, ("год", "года", "лет")) == "года"
    assert formatting.plural_ru(5, ("год", "года", "лет")) == "лет"
    assert formatting.plural_ru(11, ("год", "года", "лет")) == "лет"
    assert formatting.plural_ru(21, ("год", "года", "лет")) == "год"


def test_main_flow_with_fakes(planets_db, monkeypatch):
    """Полный main(): выбор движка, флот, умножение топлива и цены."""
    from tests.test_engine_helpers import FakeHyper

    monkeypatch.setattr(engine_hub, "load_engines", lambda *a, **k: [FakeHyper])
    res = calc.main("MW-SLR-EARTH", "MW-SLR-MARS", 100, 50)
    assert res.selected_engine == "Гипер"  # MAX_RANGE покрывает, порядок по дальности
    assert res.ships == 1
    assert res.flight_price == 5_000.0
    assert res.fuel_amount == 10.0
    assert res.flight_time > 0


def test_main_multiplies_fleet(planets_db, monkeypatch):
    from tests.test_engine_helpers import FakeRocket

    # 3 корабля по весу: 250т / 120т
    monkeypatch.setattr(engine_hub, "load_engines", lambda *a, **k: [FakeRocket])
    res = calc.main("MW-SLR-EARTH", "MW-SLR-MARS", 10, 250)
    assert res.ships == 3
    assert res.trips == 1
    assert res.fuel_amount == pytest.approx(3 * FakeRocket.calculate(
        res.distance, 250 / 3, 10 / 3, 1.0).fuel_amount)
    # время НЕ умножается
    single = FakeRocket.calculate(res.distance, 250 / 3, 10 / 3, 1.0)
    assert res.flight_time == single.flight_time


def test_main_splits_over_fleet_into_trips(planets_db, monkeypatch):
    """2000т при лимите 120т = 17 кораблей -> влезает (1 ходка);
    6000т = 50 кораблей -> 20 кораблей x 3 ходки, груз делится на все 60 слотов."""
    from tests.test_engine_helpers import FakeRocket

    monkeypatch.setattr(engine_hub, "load_engines", lambda *a, **k: [FakeRocket])
    res = calc.main("MW-SLR-EARTH", "MW-SLR-MARS", 10, 6000)
    assert res.ships == 20
    assert res.trips == 3
    slots = res.ships * res.trips
    per_slot = FakeRocket.calculate(res.distance, 6000 / slots, 10 / slots, 1.0)
    assert res.fuel_amount == pytest.approx(per_slot.fuel_amount * slots)
    assert res.flight_price == pytest.approx(per_slot.flight_price * slots)
    assert res.flight_time == per_slot.flight_time  # пачкой — без умножения
