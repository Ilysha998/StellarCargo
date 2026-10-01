# StellarCargo

Грузовые перелёты между планетами: контроллер (TUI + расчёт стоимости)
и три модуля двигателей, которые пишут участники команды.

## Структура

- `core/` — общий контракт (типы и ошибки), единственная общая точка.
- `engines/` — модули двигателей: `rocket.py`, `impulse.py`, `hyper.py` (ветки участников).
- `controller/` — контроллер: база планет, выбор двигателя, флот, TUI.
- `scripts/seed_planets.py` — заливка базы планет по маске `GLX-SYS-NAME`.
- `docs/CONTRACT.md` — контракт модуля двигателя для участников.

## Запуск

```bash
pip install -r requirements-dev.txt
python scripts/seed_planets.py      # залить data/planets.db
python -m controller                # TUI
pytest -q                           # тесты
```

## Правила веток

- `main` — только через PR и зелёные тесты.
- `Controller`, `Rocket`, `Impulse`, `Hyper` — рабочие ветки участников.
