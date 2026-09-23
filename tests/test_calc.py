import pytest

from core import FleetTooLargeError, PlanetNotFoundError, StellarCargoError
from controller import calc, db, geometry


def test_get_planet_by_id_and_name(planets_db):
    by_id = db.get_planet("MW-SLR-EARTH")
    assert by_id.gravity == 1.0
    by_name = db.get_planet("Земля")
    assert by_name.id == "MW-SLR-EARTH"


def test_get_planet_unknown(planets_db):
    with pytest.raises(PlanetNotFoundError):
        db.get_planet("НеПланета")


def test_search_planets(planets_db):
    hits = db.search_planets("Земл")
    assert any(p.id == "MW-SLR-EARTH" for p in hits)
    assert db.search_planets("") == []


def test_distance_sol_zero_and_positive(planets_db):
    earth = db.get_planet("MW-SLR-EARTH")
    mars = db.get_planet("MW-SLR-MARS")
    assert geometry.distance(earth, earth) == 0
    assert geometry.distance(earth, mars) > 0
    assert geometry.distance(earth, mars) == geometry.distance(mars, earth)


def test_ships_needed_by_mass_and_volume():
    assert calc.ships_needed(10, 10, weight_limit=100, ship_volume=1000) == 1
    assert calc.ships_needed(250, 10, weight_limit=100, ship_volume=1000) == 3
    assert calc.ships_needed(10, 3500, weight_limit=100, ship_volume=1000) == 4


def test_ships_needed_overflow():
    with pytest.raises(FleetTooLargeError):
        calc.ships_needed(10_000, 10, weight_limit=100, ship_volume=1000, max_fleet=20)


def test_main_validation(planets_db):
    with pytest.raises(StellarCargoError):
        calc.main("MW-SLR-EARTH", "MW-SLR-MARS", 0, 0)
    with pytest.raises(StellarCargoError):
        calc.main("MW-SLR-EARTH", "MW-SLR-MARS", -5, 10)
    with pytest.raises(StellarCargoError):
        calc.main("MW-SLR-EARTH", "MW-SLR-MARS", "10", 10)
