"""Работа с базой планет (SQLite).

Маска ID: GLX-SYS-NAME, например MW-SLR-EARTH.
Поля: id, display_name, galaxy, system, name, x, y, z, gravity.
Координаты — световые годы, оси правой тройки; gravity — g (Земля = 1.0).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from core import PlanetNotFoundError

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "planets.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS planets (
    id           TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    galaxy       TEXT NOT NULL,
    system       TEXT NOT NULL,
    name         TEXT NOT NULL,
    x            REAL NOT NULL,
    y            REAL NOT NULL,
    z            REAL NOT NULL,
    gravity      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_planets_display ON planets(display_name);
CREATE INDEX IF NOT EXISTS idx_planets_galaxy  ON planets(galaxy);
"""


@dataclass(frozen=True)
class Planet:
    id: str            # MW-SLR-EARTH
    display_name: str  # Земля
    galaxy: str        # MW
    system: str        # SLR
    name: str          # EARTH
    x: float
    y: float
    z: float
    gravity: float


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _row_to_planet(row: sqlite3.Row) -> Planet:
    return Planet(
        id=row["id"],
        display_name=row["display_name"],
        galaxy=row["galaxy"],
        system=row["system"],
        name=row["name"],
        x=row["x"],
        y=row["y"],
        z=row["z"],
        gravity=row["gravity"],
    )


def get_planet(key: str, db_path: Path | str | None = None) -> Planet:
    """Поиск планеты по id (MW-SLR-EARTH) или по названию.

    Название должно быть однозначным, иначе PlanetNotFoundError с подсказкой.
    """
    key = (key or "").strip()
    if not key:
        raise PlanetNotFoundError("Не указана планета.")

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM planets WHERE id = ? COLLATE NOCASE", (key,)
        ).fetchone()
        if row is None:
            rows = conn.execute(
                "SELECT * FROM planets WHERE display_name = ? COLLATE NOCASE",
                (key,),
            ).fetchall()
            if len(rows) > 1:
                ids = ", ".join(r["id"] for r in rows[:5])
                raise PlanetNotFoundError(
                    f"Название «{key}» неоднозначно ({len(rows)} совпадений): {ids}. "
                    "Укажите полный id."
                )
            if rows:
                row = rows[0]

    if row is None:
        raise PlanetNotFoundError(f"Планета «{key}» не найдена. Проверьте справочник.")
    return _row_to_planet(row)


def search_planets(
    query: str, limit: int = 8, db_path: Path | str | None = None
) -> list[Planet]:
    """Поиск для подсказок в TUI: по id, названию и составным частям."""
    query = (query or "").strip()
    if not query:
        return []
    like = f"%{query}%"
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM planets
             WHERE id           LIKE ? COLLATE NOCASE
                OR display_name LIKE ? COLLATE NOCASE
                OR galaxy       LIKE ? COLLATE NOCASE
                OR system       LIKE ? COLLATE NOCASE
                OR name         LIKE ? COLLATE NOCASE
             ORDER BY LENGTH(id), id
             LIMIT ?
            """,
            (like, like, like, like, like, limit),
        ).fetchall()
    return [_row_to_planet(r) for r in rows]
