# Relink API

Сервис сокращения ссылок на FastAPI с регистрацией, аналитикой и кэшированием через Redis.

## Описание API

### Auth
- `POST /auth/register` - регистрация пользователя и выдача JWT.
- `POST /auth/login` - логин пользователя и выдача JWT.

### Links
- `POST /links/shorten` - создать короткую ссылку (`custom_alias` и `expires_at` опциональны).
- `GET /links/{short_code}` - редирект на оригинальный URL.
- `PUT /links/{short_code}` - обновить оригинальный URL (только владелец ссылки).
- `DELETE /links/{short_code}` - удалить ссылку (только владелец ссылки).
- `GET /links/{short_code}/stats` - статистика по ссылке.
- `GET /links/search?original_url=...` - поиск по оригинальному URL.

### Дополнительные эндпоинты
- `GET /links/expired/history` - история удаленных/истекших ссылок.
- `GET /health` - health-check сервиса.

Swagger UI: `http://localhost:8000/docs`

## Примеры запросов

### 1) Регистрация
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "12345678"
  }'
```

### 2) Логин
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "12345678"
  }'
```

### 3) Создать короткую ссылку
```bash
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "original_url": "https://www.python.org",
    "custom_alias": "pyhome",
    "expires_at": "2026-03-10T12:30:00Z"
  }'
```

### 4) Получить статистику
```bash
curl "http://localhost:8000/links/pyhome/stats"
```

### 5) Поиск по original_url
```bash
curl "http://localhost:8000/links/search?original_url=https://www.python.org"
```

## Инструкция по запуску

### Docker Compose
1. Скопировать переменные окружения:
   - `cp .env.example .env`
2. Запустить сервисы:
   - `docker compose up --build`
3. Открыть:
   - API docs: `http://localhost:8000/docs`
   - Health: `http://localhost:8000/health`

### Локально
1. Создать и активировать venv:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Установить зависимости:
   - `pip install -r requirements.txt`
3. Поднять PostgreSQL и Redis (например, через Docker).
4. Настроить `.env` под локальные хосты.
5. Запустить:
   - `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Описание БД

Используется PostgreSQL как основное хранилище.

### Таблица `users`
- `id` - PK.
- `email` - уникальный email пользователя.
- `password_hash` - хэш пароля.
- `created_at` - дата регистрации.

### Таблица `links`
- `id` - PK.
- `short_code` - уникальный короткий код.
- `original_url` - оригинальный URL.
- `created_at`, `updated_at` - даты создания/обновления.
- `expires_at` - время жизни ссылки (опционально).
- `click_count` - число переходов.
- `last_accessed_at` - дата последнего перехода.
- `owner_id` - FK на `users.id` (может быть `NULL` для анонимных ссылок).

### Таблица `expired_links`
- архив удаленных/истекших/неактивных ссылок:
  `short_code`, `original_url`, `created_at`, `removed_at`, `click_count`, `owner_id`, `reason`.

Redis используется для кэширования часто запрашиваемых данных (`stats` и redirect-данные).
