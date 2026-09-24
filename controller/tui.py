"""TUI StellarCargo: экран ввода + экран расчёта (console стоимости).

Запуск:  python -m controller
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListView, ListItem, Static

from core import StellarCargoError
from . import calc, db, geometry, formatting


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
    """Мини-проекция маршрута на XY: две точки и линия между ними."""

    WIDTH = 46
    HEIGHT = 13

    def show_route(self, origin: db.Planet | None, dest: db.Planet | None) -> None:
        grid = [[" "] * self.WIDTH for _ in range(self.HEIGHT)]

        # рамка
        for x in range(self.WIDTH):
            grid[0][x] = grid[self.HEIGHT - 1][x] = "─"
        for y in range(self.HEIGHT):
            grid[y][0] = grid[y][self.WIDTH - 1] = "│"
        for gx, gy in ((0, 0), (self.WIDTH - 1, 0), (0, self.HEIGHT - 1),
                       (self.WIDTH - 1, self.HEIGHT - 1)):
            grid[gy][gx] = "┼"

        if origin is None or dest is None:
            hint = " Выберите обе планеты "
            start = max(1, (self.WIDTH - len(hint)) // 2)
            for i, ch in enumerate(hint):
                if start + i < self.WIDTH - 1:
                    grid[self.HEIGHT // 2][start + i] = ch
            self.update("\n".join("".join(r) for r in grid))
            return

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

    BINDINGS = [("escape", "back", "Назад")]

    def __init__(self, result: calc.FlightResult | None, error: str | None = None):
        super().__init__()
        self.result = result
        self.error = error

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="result-scroll"):
            if self.error:
                yield Label(self.error, id="error", classes="error")
            else:
                assert self.result is not None
                yield Label("Расчёт маршрута", id="result-title")
                with Vertical(id="result-table"):
                    for key, value in _fmt_result(self.result):
                        with Horizontal(classes="result-row"):
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


class InputScreen(Screen):
    """Экран ввода: две планеты с поиском, груз, мини-проекция."""

    def __init__(self) -> None:
        super().__init__()
        self.origin: db.Planet | None = None
        self.dest: db.Planet | None = None

    def compose(self) -> ComposeResult:
        yield Header()
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
                        yield Input(placeholder="Масса, т", id="mass", type="number")
                        yield Input(placeholder="Объём, м³", id="volume", type="number")
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
        yield Footer()

    # --- поиск -------------------------------------------------------------

    def _fill_list(self, list_id: str, query: str) -> None:
        view = self.query_one(f"#{list_id}", ListView)
        view.clear()
        try:
            planets = db.search_planets(query, limit=6)
        except StellarCargoError as exc:
            self.query_one("#input-error", Label).update(str(exc))
            return
        for p in planets:
            view.append(ListItem(Label(f"{p.display_name}  ·  {p.id}"), name=p.id))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "from":
            self._fill_list("from-list", event.value)
        elif event.input.id == "to":
            self._fill_list("to-list", event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        planet_id = event.item.name
        if not planet_id:
            return
        try:
            planet = db.get_planet(planet_id)
        except StellarCargoError as exc:
            self.query_one("#input-error", Label).update(str(exc))
            return
        if event.list_view.id == "from-list":
            self.origin = planet
            self.query_one("#from", Input).value = planet.id
            event.list_view.clear()
        elif event.list_view.id == "to-list":
            self.dest = planet
            self.query_one("#to", Input).value = planet.id
            event.list_view.clear()
        self._refresh_projection()

    # --- проекция ----------------------------------------------------------

    def _refresh_projection(self) -> None:
        self.query_one("#projection", RouteProjection).show_route(self.origin, self.dest)
        caption = self.query_one("#route-caption", Label)
        if self.origin and self.dest:
            d = geometry.distance(self.origin, self.dest)
            caption.update(
                f"{self.origin.display_name} → {self.dest.display_name} · "
                f"{formatting.format_distance(d)}"
            )
        else:
            caption.update("Ожидание выбора планет…")

    def on_mount(self) -> None:
        self._refresh_projection()

    # --- расчёт ------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "calc":
            return
        error = self.query_one("#input-error", Label)
        if self.origin is None or self.dest is None:
            error.update("Выберите обе планеты из подсказок.")
            return
        error.update("")

        def number(field_id: str) -> float:
            raw = self.query_one(f"#{field_id}", Input).value.strip().replace(",", ".")
            if not raw:
                return 0.0
            try:
                return float(raw)
            except ValueError as exc:
                raise StellarCargoError(
                    f"Поле «{field_id}» должно быть числом."
                ) from exc

        try:
            result = calc.main(
                planet_from=self.origin.id,
                planet_destination=self.dest.id,
                cargo_volume=number("volume"),
                cargo_mass=number("mass"),
            )
        except StellarCargoError as exc:
            self.app.push_screen(ResultScreen(None, error=str(exc)))
            return
        self.app.push_screen(ResultScreen(result))


class StellarCargoApp(App):
    TITLE = "StellarCargo"
    CSS = """
    #input-columns { height: auto; }
    #left-column { width: 50%; padding: 0 1; }
    #right-column { width: 50%; padding: 0 1; }
    .field-label { color: $accent; text-style: bold; margin-top: 1; }
    .planet-input { margin-bottom: 0; }
    .suggest { height: 7; border: none; background: $panel; }
    .cargo-row Input { width: 1fr; }
    #calc { margin-top: 1; width: 100%; }
    #input-error, .error { color: red; margin-top: 1; height: auto; }
    #projection {
        width: 48; height: 15;
        border: round $accent;
        background: $surface;
        color: $accent;
        content-align: center middle;
    }
    #route-caption { color: $text-muted; margin-top: 1; }
    #result-title { text-style: bold; color: $accent; margin: 1 0; }
    .result-row { height: 1; }
    .result-key { width: 18; color: $text-muted; }
    .result-value { width: 1fr; text-style: bold; }
    #result-note { margin-top: 1; color: $text-muted; height: auto; }
    #result-scroll { padding: 0 2; }
    #back { margin: 1 2; width: 30; }
    """

    def on_mount(self) -> None:
        self.push_screen(InputScreen())


def main() -> None:
    StellarCargoApp().run()


if __name__ == "__main__":
    main()
