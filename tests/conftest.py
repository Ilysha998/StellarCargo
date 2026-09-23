import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controller import db  # noqa: E402
from scripts.seed_planets import seed  # noqa: E402


@pytest.fixture()
def planets_db(tmp_path):
    path = tmp_path / "planets.db"
    seed(path)
    return path


@pytest.fixture(autouse=True)
def use_db(planets_db, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", planets_db)
