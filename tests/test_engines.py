import pytest

from core import EngineContractError, EngineResult, EngineSelectionError
from controller import engines as engine_hub
from tests.test_engine_helpers import FakeHyper, FakeRocket


def test_validate_engine_accepts_contract():
    import types

    mod = types.ModuleType("engines.fake")
    mod.NAME = "X"
    mod.MAX_RANGE = 10.0
    mod.WEIGHT_LIMIT = 1.0
    mod.calculate = lambda *a: None
    engine_hub.validate_engine(mod)


def test_validate_engine_rejects_missing_attr():
    import types

    mod = types.ModuleType("engines.broken")
    mod.NAME = "X"
    mod.MAX_RANGE = 10.0
    # нет WEIGHT_LIMIT и calculate
    with pytest.raises(EngineContractError):
        engine_hub.validate_engine(mod)


def test_validate_engine_rejects_bad_range():
    import types

    mod = types.ModuleType("engines.bad")
    mod.NAME = "X"
    mod.MAX_RANGE = -5
    mod.WEIGHT_LIMIT = 1.0
    mod.calculate = lambda *a: None
    with pytest.raises(EngineContractError):
        engine_hub.validate_engine(mod)


def test_select_engine_picks_by_distance():
    engine_list = [FakeRocket, FakeHyper]
    assert engine_hub.select_engine(50, engine_list).NAME == "Ракетный"
    assert engine_hub.select_engine(150, engine_list).NAME == "Гипер"


def test_select_engine_empty():
    with pytest.raises(EngineSelectionError):
        engine_hub.select_engine(10, [])


def test_call_engine_wraps_bad_return():
    import types

    mod = types.ModuleType("engines.wrong")
    mod.NAME = "Кривой"
    mod.calculate = lambda *a: "не EngineResult"
    with pytest.raises(EngineContractError):
        engine_hub.call_engine(mod, 1, 1, 1, 1)


def test_call_engine_rejects_negative_time():
    import types

    mod = types.ModuleType("engines.neg")
    mod.NAME = "Отрицательный"
    mod.calculate = lambda *a: EngineResult(1, 1, 1, -5)
    with pytest.raises(EngineContractError):
        engine_hub.call_engine(mod, 1, 1, 1, 1)
