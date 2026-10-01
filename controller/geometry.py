"""Геометрия маршрута: 3D-расстояние в световых годах."""

from __future__ import annotations

import math

from .db import Planet


def distance(a: Planet, b: Planet) -> float:
    """Евклидово расстояние между двумя планетами, световые годы."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)
