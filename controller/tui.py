"""TUI StellarCargo: экран ввода + экран расчёта (console стоимости).

Запуск:  python -m controller
"""

from __future__ import annotations

import math
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Static
from textual_image.widget import Image

from core import StellarCargoError
from . import calc, db, engines as engine_hub, formatting, geometry

LOGO_PATH = Path(__file__).resolve().parent.parent / "images" / "Cybersun_logo.png"

# ASCII-логотип Cybersun: pyfiglet, шрифт "small".
# Генерация: python -c "import pyfiglet; print(pyfiglet.figlet_format('CYBERSUN', font='small'))"
BANNER = r"""  _____   _____ ___ ___  ___ _   _ _  _
 / __\ \ / / _ ) __| _ \/ __| | | | \| |
| (__ \ V /| _ \ _||   /\__ \ |_| | .` |
 \___| |_| |___/___|_|_\|___/\___/|_|\_|"""


class BrandHeader(Horizontal):
    """Верхний блок: логотип Cybersun + ASCII-баннер + названия."""

    def compose(self) -> ComposeResult:
        if LOGO_PATH.exists():
            yield Image(LOGO_PATH, id="brand-logo")
        with Vertical(id="brand-text"):
            yield Static(BANNER, id="brand-banner", markup=False)
            yield Label("Cybersun Logistics", id="brand-name")
        with Vertical(id="brand-app"):
            yield Label("StellarCargo", id="app-title")
            yield Label("консоль перевозок", id="app-sub")


def _fmt_result(res: calc.FlightResult) -> list[tuple[str, str]]:
    """Пары (метка, значение) для экрана результата — та же строка вывода main()."""
    return [
        ("Двигатель", res.selected_engine),
        ("Расстояние", formatting.format_distance(res.distance)),
        ("Кораблей", str(res.ships)),
        ("Ходок", str(res.trips)),
        ("Время в пути", formatting.format_duration(res.flight_time)),
        ("Топливо", formatting.format_tonnes(res.fuel_amount)),
        ("Расход", f"{formatting.format_tonnes(res.fuel_consumption)}/ч на корабль"),
        ("Цена", formatting.format_money(res.flight_price)),
        ("Откуда", f"{res.origin.display_name} ({res.origin.id})"),
        ("Куда", f"{res.destination.display_name} ({res.destination.id})"),
    ]


class RouteProjection(Static):
    """Мини-проекция маршрута на XY: две точки и линия между ними.

    Рамку рисует только CSS (border: round) — внутренний ASCII-каркас убран,
    он давал двойную рамку с косыми углами.
    """

    WIDTH = 46
    HEIGHT = 13

    def show_route(self, origin: db.Planet | None, dest: db.Planet | None) -> None:
        if origin is None or dest is None:
            # content-align: center middle в CSS центрирует подсказку
            self.update("Выберите обе планеты")
            return

        grid = [[" "] * self.WIDTH for _ in range(self.HEIGHT)]

        pts = [origin, dest]
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-9)
        span_y = max(max_y - min_y, 1e-9)

        def to_cell(p: db.Planet) -> tuple[int, int]:
            cx = 2 + int((p.x - min_x) / span_x * (self.WIDTH - 4))
            cy = self.HEIGHT - 3 - int((p.y - min_y) / span_y * (self.HEIGHT - 3))
            return max(1, min(self.WIDTH - 2, cx)), max(1, min(self.HEIGHT - 2, cy))

        ax, ay = to_cell(origin)
        bx, by = to_cell(dest)

        steps = max(abs(bx - ax), abs(by - ay), 1)
        for i in range(steps + 1):
            x = round(ax + (bx - ax) * i / steps)
            y = round(ay + (by - ay) * i / steps)
            if 0 < y < self.HEIGHT - 1 and 0 < x < self.WIDTH - 1:
                grid[y][x] = "·"
        grid[ay][ax] = "○"
        grid[by][bx] = "◆"

        self.update("\n".join("".join(r) for r in grid))


class ResultScreen(Screen):
    """Экран расчёта: строка вывода main() + кнопки."""

    BINDINGS = [
        ("escape", "back", "Назад"),
        ("ctrl+q", "quit", "Выход"),
    ]

    def __init__(self, result: calc.FlightResult | None, error: str | None = None):
        super().__init__()
        self.result = result
        self.error = error

    def compose(self) -> ComposeResult:
        yield BrandHeader(id="brand")
        with VerticalScroll(id="result-scroll"):
            if self.error:
                yield Label("Ошибка расчёта", id="result-title")
                yield Label(self.error, id="error", classes="error")
            else:
                assert self.result is not None
                yield Label(
                    f"{self.result.origin.display_name} → "
                    f"{self.result.destination.display_name}",
                    id="result-title",
                )
                with Vertical(id="result-table"):
                    for key, value in _fmt_result(self.result):
                        row_classes = "result-row money" if key == "Цена" else "result-row"
                        with Horizontal(classes=row_classes):
                            yield Label(key, classes="result-key")
                            yield Label(value, classes="result-value")
                yield Label(
                    "Формат: выбран один двигатель по дальности; топливо и цена "
                    "умножены на число ходок, время — флот летит пачкой.",
                    id="result-note",
                )
        yield Button("← К вводу", id="back", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()

    def action_back(self) -> None:
        """У Screen нет унаследованного action_back (он у App) — биндинг ищет его здесь."""
        self.app.pop_screen()


class InputScreen(Screen):
    """Экран ввода: две планеты с поиском, груз, мини-проекция."""

    BINDINGS = [("ctrl+q", "quit", "Выход")]

    def __init__(self) -> None:
        super().__init__()
        self.origin: db.Planet | None = None
        self.dest: db.Planet | None = None
        # id-планет, показанных в подсказках (для выбора по Enter)
        self._suggestions: dict[str, list[str]] = {}

    def compose(self) -> ComposeResult:
        yield BrandHeader(id="brand")
        with VerticalScroll(id="input-scroll"):
            with Horizontal(id="input-columns"):
                with Vertical(id="left-column"):
                    yield Label("Планета вылета", classes="field-label")
                    yield Input(placeholder="id или название: MW-SLR-EARTH / Земля",
                                id="from", classes="planet-input")
                    yield ListView(id="from-list", classes="suggest")
                    yield Label("Планета назначения", classes="field-label")
                    yield Input(placeholder="id или название планеты",
                                id="to", classes="planet-input")
                    yield ListView(id="to-list", classes="suggest")
                    yield Label("Груз", classes="field-label")
                    with Horizontal(classes="cargo-row"):
                        yield Input(placeholder="Масса, т", id="mass")
                        yield Input(placeholder="Объём, м³", id="volume")
                    yield Button("Рассчитать перелёт →", id="calc",
                                 variant="primary")
                    yield Label("", id="input-error", classes="error")
                with Vertical(id="right-column"):
                    yield Label("Маршрут (проекция XY)", classes="field-label")
                    yield RouteProjection(id="projection")
                    yield Label(
                        "Ожидание выбора планет…",
                        id="route-caption",
                    )
                    yield Label("Как считаем", classes="field-label")
                    yield Static(id="rules", classes="info")
                    yield Label("Двигатели (по дальности)", classes="field-label")
                    yield Static(id="engine-legend", classes="info")
        yield Footer()

    # --- подсказки и выбор планеты -----------------------------------------

    async def _fill_list(self, list_id: str, query: str) -> None:
        view = self.query_one(f"#{list_id}", ListView)
        await view.clear()
        try:
            planets = db.search_planets(query, limit=6)
        except StellarCargoError as exc:
            self.query_one("#input-error", Label).update(str(exc))
            self._suggestions[list_id] = []
            view.display = False
            return
        for p in planets:
            await view.append(ListItem(Label(f"{p.display_name}  ·  {p.id}"), name=p.id))
        self._suggestions[list_id] = [p.id for p in planets]
        # пустая подсказка не должна оставлять мёртвый прямоугольник
        view.display = bool(planets)

    async def _select_planet(self, list_id: str, planet_id: str) -> None:
        try:
            planet = db.get_planet(planet_id)
        except StellarCargoError as exc:
            self.query_one("#input-error", Label).update(str(exc))
            return
        if list_id == "from-list":
            self.origin = planet
            field_id = "from"
        else:
            self.dest = planet
            field_id = "to"
        # правка value вызовет Input.Changed — обработчик ниже спрячет подсказку
        self.query_one(f"#{field_id}", Input).value = planet.id
        view = self.query_one(f"#{list_id}", ListView)
        await view.clear()
        view.display = False
        self._suggestions[list_id] = []
        self.query_one("#input-error", Label).update("")
        self._refresh_projection()
        self._focus_after_planet(field_id)

    def _focus_after_planet(self, field_id: str) -> None:
        """Поток ввода: вылет -> назначение -> груз."""
        if field_id == "from" and self.dest is None:
            self.query_one("#to", Input).focus()
        elif self.origin is not None and self.dest is not None:
            self.query_one("#mass", Input).focus()

    async def on_input_changed(self, event: Input.Changed) -> None:
        self.query_one("#input-error", Label).update("")
        if event.input.id not in ("from", "to"):
            return
        list_id = f"{event.input.id}-list"
        selected = self.origin if event.input.id == "from" else self.dest
        if selected is not None and event.value == selected.id:
            # программная установка id после выбора — подсказку просто прячем
            view = self.query_one(f"#{list_id}", ListView)
            await view.clear()
            view.display = False
            return
        if selected is not None:
            # текст правили вручную — прежний выбор больше не действителен
            if event.input.id == "from":
                self.origin = None
            else:
                self.dest = None
            self._refresh_projection()
        await self._fill_list(list_id, event.value)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        planet_id = event.item.name
        if planet_id:
            await self._select_planet(event.list_view.id, planet_id)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter: в поле планеты — выбрать первый вариант, в грузе — считать."""
        iid = event.input.id
        if iid in ("from", "to"):
            candidates = self._suggestions.get(f"{iid}-list", [])
            if candidates:
                await self._select_planet(f"{iid}-list", candidates[0])
        elif iid in ("mass", "volume"):
            self._do_calc()

    # --- проекция ----------------------------------------------------------

    def _refresh_projection(self) -> None:
        self.query_one("#projection", RouteProjection).show_route(self.origin, self.dest)
        caption = self.query_one("#route-caption", Label)
        if self.origin and self.dest:
            dist = geometry.distance(self.origin, self.dest)
            lines = [
                f"{self.origin.display_name} → {self.dest.display_name} · "
                f"{formatting.format_distance(dist)}",
                f"гравитация вылета: {self.origin.gravity:.2f}",
            ]
            try:
                engine = engine_hub.select_engine(dist)
            except StellarCargoError:
                pass  # модули ещё не сведены — легенда внизу покажет статус
            else:
                lines.append(f"движок: {engine.NAME}")
            caption.update("\n".join(lines))
        else:
            caption.update("Ожидание выбора планет…")

    @staticmethod
    def _rules_text() -> str:
        volume = f"{calc.SHIP_VOLUME:,.0f}".replace(",", " ")
        return (
            "— выбор двигателя только по расстоянию\n"
            f"— слот груза {volume} м³, флот до {calc.MAX_FLEET} кораблей\n"
            "— время флота общее, топливо и цена умножаются на число слотов\n"
            "— стартовое топливо зависит от гравитации планеты вылета"
        )

    @staticmethod
    def _engine_legend_text() -> str:
        try:
            found = engine_hub.load_engines()
        except StellarCargoError as exc:
            return f"— {exc}"
        if not found:
            return "— модули двигателей не подключены"
        lines = [
            f"— {m.NAME}: до {formatting.format_distance(m.MAX_RANGE)}"
            for m in sorted(found, key=lambda m: m.MAX_RANGE)
        ]
        return "\n".join(lines)

    def on_mount(self) -> None:
        self.query_one("#rules", Static).update(self._rules_text())
        self.query_one("#engine-legend", Static).update(self._engine_legend_text())
        self._refresh_projection()

    # --- расчёт ------------------------------------------------------------

    def _do_calc(self) -> None:
        error = self.query_one("#input-error", Label)
        if self.origin is None or self.dest is None:
            error.update("Выберите обе планеты из подсказок.")
            return
        try:
            volume = self._parse_number("volume", "Объём")
            mass = self._parse_number("mass", "Масса")
        except StellarCargoError as exc:
            error.update(str(exc))
            return
        if volume == 0 and mass == 0:
            error.update("Укажите массу и/или объём груза.")
            return
        error.update("")
        try:
            result = calc.main(
                planet_from=self.origin.id,
                planet_destination=self.dest.id,
                cargo_volume=volume,
                cargo_mass=mass,
            )
        except StellarCargoError as exc:
            self.app.push_screen(ResultScreen(None, error=str(exc)))
            return
        self.app.push_screen(ResultScreen(result))

    def _parse_number(self, field_id: str, title: str) -> float:
        raw = self.query_one(f"#{field_id}", Input).value.strip()
        raw = raw.replace(" ", "").replace(",", ".")
        if not raw:
            return 0.0
        try:
            value = float(raw)
        except ValueError as exc:
            raise StellarCargoError(
                f"{title}: введите число (можно через запятую)."
            ) from exc
        if not math.isfinite(value) or value < 0:
            raise StellarCargoError(
                f"{title}: нужно обычное неотрицательное число."
            )
        return value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "calc":
            self._do_calc()


class StellarCargoApp(App):
    TITLE = "StellarCargo"
    CSS = """
    #brand { height: auto; background: $panel; padding: 1 2; align: left middle; }
    #brand-logo { width: 10; height: auto; margin-right: 2; }
    #brand-text { width: auto; height: auto; }
    #brand-banner { color: $accent; height: auto; }
    #brand-name { color: $text-muted; text-style: bold; }
    #brand-app { width: 1fr; height: auto; align: right middle; }
    #brand-app Label { text-align: right; }
    #app-title { text-style: bold; }
    #app-sub { color: $text-muted; }
    #input-columns { height: auto; }
    #left-column { width: 1fr; height: auto; padding: 0 1; }
    #right-column { width: 52; height: auto; padding: 0 1; }
    .field-label { color: $accent; text-style: bold; margin-top: 1; }
    .planet-input { margin-bottom: 0; }
    .suggest {
        display: none;
        height: auto;
        border: none;
        background: $panel;
        padding: 0 1;
    }
    .cargo-row { height: auto; }
    .cargo-row Input { width: 1fr; }
    #calc {
        margin-top: 1;
        width: 100%;
        background: $accent;
        color: #1a1200;
        border: none;
        text-style: bold;
    }
    #calc:hover { background: #ffc266; }
    #calc.-active { background: #e5941f; }
    #calc:focus { text-style: bold underline; }
    #input-error { color: $error; margin-top: 1; height: auto; }
    #projection {
        width: 48; height: 15;
        border: round $accent;
        background: $surface;
        color: $accent;
        content-align: center middle;
    }
    #route-caption { color: $text-muted; margin-top: 1; height: auto; }
    .info {
        height: auto;
        color: $text-muted;
        background: $surface;
        border: round;
        padding: 1 2;
    }
    #result-title { text-style: bold; color: $accent; margin: 1 0 0 0; height: auto; }
    #result-table {
        background: $surface;
        border: round;
        padding: 1 2;
        height: auto;
        width: auto;
        margin-top: 1;
        margin-bottom: 1;
    }
    .result-row { height: 1; }
    .result-key { width: 18; color: $text-muted; }
    .result-value { width: 1fr; text-style: bold; }
    .result-row.money .result-value { color: $accent; }
    #result-note { margin-top: 1; color: $text-muted; height: auto; }
    #result-scroll { padding: 0 2; }
    #back {
        margin: 1 2;
        width: 30;
        border: tall $accent;
        color: $accent;
        background: $panel;
        text-style: bold;
    }
    #back:hover { background: $accent; color: #1a1200; }
    .error { color: $error; height: auto; }
    #error { border: round $error; padding: 1 2; margin-top: 1; }
    """

    def on_mount(self) -> None:
        self.push_screen(InputScreen())


def main() -> None:
    StellarCargoApp().run()


if __name__ == "__main__":
    main()
