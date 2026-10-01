# Контракт модуля двигателя

Единственный общий файл между контроллером и участниками — `core/__init__.py`.
Ваш модуль лежит в `engines/` (своя ветка: `Rocket`, `Impulse`, `Hyper`)
и **не импортирует** ни контроллер, ни базу данных, ничего не печатает.

## Обязательные атрибуты модуля

| Атрибут | Тип | Смысл |
|---|---|---|
| `NAME` | `str` | имя тира для вывода, например `"Ракетный"` |
| `MAX_RANGE` | `float` | максимальная дальность, **световые годы** |
| `WEIGHT_LIMIT` | `float` | максимум груза на **один корабль**, тонн |
| `calculate(...)` | функция | см. ниже |

## Сигнатура calculate

```python
def calculate(distance: float, cargo_mass: float, cargo_volume: float, gravity: float) -> EngineResult:
```

Вход — данные **одного корабля** (груз уже поделён контроллером):

| Параметр | Единицы |
|---|---|
| `distance` | световые годы |
| `cargo_mass` | тонны |
| `cargo_volume` | м³ |
| `gravity` | g, гравитация **планеты вылета** (Земля = 1.0) |

## Возврат

`core.EngineResult(fuel_consumption, fuel_amount, flight_price, flight_time)`:

| Поле | Единицы | Смысл |
|---|---|---|
| `fuel_consumption` | т/ч | интенсивность расхода, на флот **не** умножается |
| `fuel_amount` | т | суммарно на корабль: пуск от гравитации + крейсер |
| `flight_price` | ₽ | за корабль |
| `flight_time` | с | время в пути (> 0) |

Константы вашего тира (цена топлива, скорость, формула пуска) — **внутри
вашего файла**, общего конфига в проекте нет.

Ошибки: кидайте `ValueError`/`ZeroDivisionError` на кривых данных — контроллер
обернёт в `EngineContractError` и покажет в TUI. Отрицательные числа и
неконечные значения в `EngineResult` контроллер отвергает сам.

Константа `LOADING_S` (погрузка перед вылетом) в ваших модулях — внутренняя
часть `flight_time`; контроллер её не читает. Если флоту приходится летать
ходками (груз не влезает в один вылет), контроллер умножает весь
`flight_time` на число ходок — движок всегда считает ОДИН перелёт.

## Шаблон

```python
# engines/rocket.py  (ветка Rocket)
from core import EngineResult

NAME = "Ракетный"
MAX_RANGE = 100.0       # св. лет — звёздная система
WEIGHT_LIMIT = 120.0    # т на корабль

def calculate(distance, cargo_mass, cargo_volume, gravity):
    # свой микроконфиг здесь: цена топлива, скорость, стартовый импульс
    fuel_launch = gravity * (cargo_mass + 40.0) * 0.15
    cruise_time = distance / 0.0008          # с
    fuel_cruise = cargo_mass * 0.0002 * cruise_time / 3600
    fuel_amount = fuel_launch + fuel_cruise
    return EngineResult(
        fuel_consumption=fuel_amount / max(cruise_time / 3600, 1.0),
        fuel_amount=fuel_amount,
        flight_price=fuel_amount * 78_000.0 + cruise_time / 86_400 * 15_000.0,
        flight_time=cruise_time,
    )
```

Проверка у себя:

```bash
python -c "from controller.engines import load_engines; print(load_engines())"
pytest -q
```
