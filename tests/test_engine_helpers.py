"""Фейковые двигатели для тестов контракта контроллера."""

from core import EngineResult


class FakeRocket:
    NAME = "Ракетный"
    MAX_RANGE = 100.0
    WEIGHT_LIMIT = 120.0

    @staticmethod
    def calculate(distance, cargo_mass, cargo_volume, gravity):
        assert distance >= 0
        assert cargo_mass >= 0
        assert gravity > 0
        fuel = (cargo_mass + gravity * 10) * 0.5
        time = distance * 100 + 60
        return EngineResult(
            fuel_consumption=fuel / (time / 3600),
            fuel_amount=fuel,
            flight_price=fuel * 1000 + time,
            flight_time=time,
        )


class FakeHyper:
    NAME = "Гипер"
    MAX_RANGE = 1e9
    WEIGHT_LIMIT = 500.0

    @staticmethod
    def calculate(distance, cargo_mass, cargo_volume, gravity):
        time = distance * 2 + 10
        return EngineResult(
            fuel_consumption=1.0,
            fuel_amount=10.0,
            flight_price=5_000.0,
            flight_time=time,
        )
