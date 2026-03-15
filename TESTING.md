# testing guide

## 1) установка зависимостей для тестов

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-test.txt
```

## 2) запуск unit + functional тестов

```bash
pytest tests -v
```

## 3) подсчет покрытия (текст + html)

```bash
coverage run -m pytest tests
coverage report -m
coverage html
```

после команды `coverage html` отчет будет лежать в `htmlcov/index.html`.

## 4) нагрузочное тестирование (locust)

1. подними api локально (`docker compose up --build` или локальный `uvicorn`).
2. запусти:

```bash
locust -f locustfile.py --host http://localhost:8000
```

3. открой web-ui locust: `http://localhost:8089`.

### headless-пример

```bash
locust -f locustfile.py --host http://localhost:8000 --headless -u 30 -r 5 -t 1m
```

готовый пример отчета приложен в `LOAD_TEST_REPORT.md`.

## 5) что покрыто тестами

- unit: `security`, `shortener`, `cleanup`.
- functional: `auth`, `links` (create/search/stats/update/delete/redirect), валидация и права доступа.
- direct-unit: отдельные тесты логики (`app/api/auth.py`, `app/api/links.py`) с моками зависимостей.
