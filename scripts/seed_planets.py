"""Заливка базы планет по маске GLX-SYS-NAME.

Запуск:  python scripts/seed_planets.py [--db data/planets.db]

Генерирует несколько галактик, систем и планет с координатами
и гравитацией. Планеты Солнечной системы заданы вручную как пример
маски (MW-SLR-EARTH). Идемпотентен: таблица пересоздаётся.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from controller import db  # noqa: E402

# Галактика: код, название, центр (x, y, z) в св. годах, радиус, кол-во систем
GALAXIES = [
    ("MW",  "Млечный Путь",                       (0.0, 0.0, 0.0),        50_000.0, 6),
    ("LMC", "Большое Магелланово Облако",         (160_000.0, 0.0, -20_000.0), 15_000.0, 3),
    ("AND", "Андромеда",                          (2_500_000.0, 0.0, 300_000.0), 80_000.0, 5),
    ("TRI", "Треугольника",                       (2_700_000.0, -400_000.0, -500_000.0), 60_000.0, 4),
]

# Пример маски вручную: MW-SLR-* (Солнечная система)
SOLAR_SYSTEM = [
    ("EARTH",  "Земля",     1.00,       1.00),
    ("MARS",   "Марс",      0.38,       1.52),
    ("VENUS",  "Венера",    0.91,       0.72),
    ("JUPITER","Юпитер",    2.53,       5.20),
    ("NEPTUNE","Нептун",    1.14,       30.05),
    ("TITAN",  "Титан",     1.35,       9.54),
]

SYSTEM_NAMES = [
    "SLR", "ALF", "BET", "GAM", "DEL", "EPS", "ZET", "ETA", "THI",
    "KAP", "LAM", "SIG", "PSI", "OMI", "RHO", "TAU", "UPS", "PHI",
]
PLANET_NAMES = [
    "PRIME", "NOVA", "HAVEN", "BARREN", "VERDANT", "FORGE", "EXILE",
    "DUSK", "DAWN", "BASTION", "REACH", "MERIDIAN", "ANVIL", "HOLLOW",
    "CROWN", "SHARD", "EMBER", "GLACIS", "TEMPEST", "HALCYON",
]
PLANET_TITLES = [
    "Примус", "Нова", "Хейвен", "Пустынный", "Зелёный", "Кузница",
    "Изгнание", "Сумерки", "Рассвет", "Бастион", "Рич", "Меридиан",
    "Наковальня", "Пустота", "Корона", "Осколок", "Угль", "Ледник",
    "Гроза", "Алкионида",
]


def _rand_point(rng: random.Random, center: tuple[float, float, float], radius: float):
    # равномерно в сфере
    while True:
        x, y, z = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)
        if x * x + y * y + z * z <= 1.0:
            return (
                center[0] + x * radius,
                center[1] + y * radius,
                center[2] + z * radius,
            )


def seed(db_path: Path | str | None = None) -> int:
    rng = random.Random(42)  # детерминированная вселенная
    rows: list[tuple] = []

    # 1) Солнечная система — маска вручную, 1 а.е. = 0.00000475 св. года
    AU_IN_LY = 4.75e-6
    system_center = (0.0, 0.0, 0.0)
    for name, title, gravity, au in SOLAR_SYSTEM:
        rows.append((
            f"MW-SLR-{name}", title, "MW", "SLR", name,
            system_center[0] + au * AU_IN_LY,
            system_center[1],
            system_center[2],
            gravity,
        ))

    used_system_codes = {"SLR"}

    for g_code, _g_name, g_center, g_radius, n_systems in GALAXIES:
        for s_idx in range(n_systems):
            if g_code == "MW" and s_idx == 0:
                s_code, s_center = "SLR", system_center  # уже добавлена выше
            else:
                free = [c for c in SYSTEM_NAMES if c not in used_system_codes]
                if not free:
                    free = [f"{c}{s_idx}" for c in SYSTEM_NAMES]
                s_code = free[0]
                used_system_codes.add(s_code)
                s_center = _rand_point(rng, g_center, g_radius)

            if g_code == "MW" and s_idx == 0:
                continue  # планеты SLR уже записаны

            for p_idx, (p_code, p_title) in enumerate(
                zip(PLANET_NAMES, PLANET_TITLES)
            ):
                if p_idx >= rng.randint(4, len(PLANET_NAMES)):
                    break
                x, y, z = _rand_point(rng, s_center, rng.uniform(50.0, 500.0))
                rows.append((
                    f"{g_code}-{s_code}-{p_code}",
                    f"{p_title}-{s_idx + 1}{'' if g_code == 'MW' else ' ' + g_code}",
                    g_code, s_code, p_code,
                    x, y, z,
                    round(rng.uniform(0.05, 3.0), 2),
                ))

    with db.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS planets")
        conn.executescript(db._SCHEMA)  # noqa: SLF001 — тот же модуль
        conn.executemany(
            """
            INSERT INTO planets (id, display_name, galaxy, system, name, x, y, z, gravity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Заливка базы планет StellarCargo")
    parser.add_argument("--db", default=None, help="путь к файлу базы")
    args = parser.parse_args()
    count = seed(args.db)
    path = args.db or db.DB_PATH
    print(f"Готово: {count} планет записано в {path}")


if __name__ == "__main__":
    main()
