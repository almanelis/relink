# load testing report

нагрузочное тестирование выполнено `locust` в headless-режиме.

## конфигурация прогона

- команда:
  `locust -f locustfile.py --host http://127.0.0.1:8001 --headless -u 15 -r 5 -t 10s`
- профиль: `RelinkUser` из `locustfile.py`
- endpoint-ы:
  - `POST /links/shorten`
  - `GET /links/{short_code}`
  - `GET /links/{short_code}/stats`

## итоговые метрики (финальный прогон)

- всего запросов: `221`
- ошибок: `0 (0.00%)`
- суммарный throughput: `22.40 req/s`
- среднее время ответа (aggregated): `11 ms`

### по endpoint-ам

- `POST /links/shorten`
  - `113` запросов
  - `0%` ошибок
  - среднее: `12 ms`
- `GET /links/{short_code}`
  - `75` запросов
  - `0%` ошибок
  - среднее: `10 ms`
- `GET /links/{short_code}/stats`
  - `33` запроса
  - `0%` ошибок
  - среднее: `6 ms`

## заметки

- в `locustfile.py` для редиректа установлен `allow_redirects=False`, чтобы замерять именно API-сервис, а не внешний сайт назначения.
