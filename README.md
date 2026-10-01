# Техническое задание: Разработка сервиса управления заказами

**Направление:** Python

---

## 1. Введение

Разработать сервис управления заказами на **FastAPI**, поддерживающий аутентификацию, работу с очередями сообщений, кеширование и фоновую обработку задач.

## 2. Функциональные требования

### 2.1 API эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| `POST` | `/register/` | Регистрация пользователя (email, пароль) |
| `POST` | `/token/` | Получение JWT-токена (OAuth2) |
| `POST` | `/orders/` | Создание заказа (только авторизованные) |
| `GET` | `/orders/{order_id}/` | Получение заказа (сначала из Redis) |
| `PATCH` | `/orders/{order_id}/` | Обновление статуса заказа |
| `GET` | `/orders/user/{user_id}/` | Получение заказов пользователя |

### 2.2 База данных (PostgreSQL)

Таблица `orders`:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | Primary key |
| `user_id` | int | ForeignKey на пользователей |
| `items` | JSON | Список товаров |
| `total_price` | float | Сумма заказа |
| `status` | enum | `PENDING`, `PAID`, `SHIPPED`, `CANCELED` |
| `created_at` | datetime | Дата создания |

### 2.3 Очереди сообщений (Kafka / RabbitMQ)

- RabbitMQ/Kafka используется как брокер сообщений между сервисами (**event-bus**), а не как брокер Celery.
- При создании заказа сервис публикует событие `new_order` в очередь.
- Отдельный consumer (отдельный процесс/сервис) подписывается на очередь, получает сообщения `new_order`, выполняет обработку и запускает фоновую задачу в Celery/taskiq.
- Celery/taskiq используется **только** для выполнения фоновых задач и не читает RabbitMQ/Kafka напрямую как event-bus.

### 2.4 Redis (кеширование заказов)

- Если заказ запрашивается повторно — отдавать его из кеша (**TTL = 5 минут**).
- При изменении заказа — обновлять кеш.

### 2.5 Celery/taskiq (фоновая обработка)

Фоновая задача обработки заказа:

```python
time.sleep(2)
print(f"Order {order_id} processed")
```

### 2.6 Безопасность

- JWT-аутентификация (OAuth2 Password Flow).
- CORS-защита (ограничение кросс-доменных запросов).
- Rate limiting (ограничение частоты запросов на API).
- SQL-инъекции — только ORM-запросы.

## 3. Нефункциональные требования

- Использование FastAPI с Pydantic.
- Работа с PostgreSQL через SQLAlchemy + Alembic.
- Асинхронное взаимодействие с Kafka / RabbitMQ.
- Docker Compose для развертывания всей инфраструктуры.
- Код должен быть структурированным и документированным.

## 4. Инструкция по сдаче

1. Разместить код на GitHub / GitLab.
2. Описать установку и запуск в `README.md`.
3. Прислать ссылку на репозиторий.
4. Обязателен **SwaggerUI**.

## 5. Критерии приёмки

- [ ] Работоспособность всех API, описанных в ТЗ
- [ ] Корректная авторизация и защита эндпоинтов
- [ ] Реальная работа Redis, брокера сообщений и фоновых задач
- [ ] Возможность развернуть проект через `docker-compose`
- [ ] Наличие и актуальность Swagger и `README.md`
- [ ] Соответствие реализации бизнес-сценариям, описанным в ТЗ
- [ ] Корректная обработка ошибок и возврат соответствующих HTTP-статусов
- [ ] Соблюдение заявленного технологического стека
- [ ] Отсутствие хардкода чувствительных данных и конфигураций

---

# Реализация: установка и запуск

## Архитектура

```
client ─▶ api (FastAPI) ──▶ PostgreSQL            (заказы, пользователи; SQLAlchemy + Alembic)
            │   └────────▶ Redis                  (кеш заказов TTL 5 мин, rate limiting)
            └─ new_order ▶ Kafka (топик orders) ─▶ consumer ─▶ Celery (брокер Redis) ─▶ worker
```

| Сервис | Назначение |
|--------|-----------|
| `api` | FastAPI-приложение, Swagger UI |
| `migrate` | одноразовый запуск `alembic upgrade head` перед стартом `api` |
| `consumer` | читает `new_order` из Kafka и ставит задачу `process_order` в Celery |
| `worker` | Celery-воркер, выполняет фоновую обработку заказа |
| `kafka-init` | одноразово создаёт топик заказов (автосоздание в Kafka отключено) |
| `postgres`, `redis`, `kafka`, `kafka-ui` | инфраструктура |

Kafka — event-bus между сервисами; Celery читает только Redis и Kafka напрямую не использует.

## Запуск

1. Создать файл окружения и заполнить пустые значения (`POSTGRES_*`, `JWT_SECRET`):

   ```bash
   cp .env.blank .env
   # JWT_SECRET можно сгенерировать так:
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Поднять всё одной командой:

   ```bash
   docker compose up --build
   ```

3. Открыть Swagger UI: <http://localhost:8000/docs> (порт задаётся `APP_PORT`).
   Kafka UI: <http://localhost:8080>.

Для авторизации в Swagger нажмите **Authorize** и введите email в поле `username` и пароль.

## Пример сценария

```bash
curl -X POST localhost:8000/register/ -H 'Content-Type: application/json' \
     -d '{"email": "user@example.com", "password": "password123"}'

curl -X POST localhost:8000/token/ -d 'username=user@example.com&password=password123'
# -> {"access_token": "<JWT>", "token_type": "bearer"}

curl -X POST localhost:8000/orders/ -H 'Authorization: Bearer <JWT>' -H 'Content-Type: application/json' \
     -d '{"items": [{"sku": "A-1", "qty": 2, "price": "10.50"}]}'
# в логах worker: "Order <id> processed"
```

## Поведение и ограничения

- Заказы доступны только владельцу: чужой заказ — `404`, чужой `user_id` в `/orders/user/{user_id}/` — `403`.
- Допустимые переходы статусов: `PENDING → PAID | CANCELED`, `PAID → SHIPPED | CANCELED`; иначе `409`.
- `GET /orders/{id}/` сначала читает Redis (TTL 5 минут); `PATCH` обновляет кеш. При недоступности Redis API читает данные из БД.
- Rate limiting: `RATE_LIMIT_REQUESTS` запросов за `RATE_LIMIT_WINDOW_SECONDS` секунд с одного IP, иначе `429` с заголовком `Retry-After`.
- CORS: разрешены только Origin из `CORS_ORIGINS` (через запятую).
- Если Kafka недоступна в момент создания заказа, заказ сохраняется, а ошибка публикации пишется в лог (паттерн outbox не реализован).
- Все настройки и секреты берутся из окружения (`.env` не коммитится).

## Локальная разработка без Docker

```bash
uv sync
# в .env указать POSTGRES_HOST/REDIS_HOST/KAFKA_BOOTSTRAP_SERVERS на локальные сервисы
alembic upgrade head
uvicorn orders_microservice_fastapi.main:app --reload
celery -A orders_microservice_fastapi.worker.celery worker -Q default
python -m orders_microservice_fastapi.consumer
```

Новая миграция: `alembic revision --autogenerate -m "message"`.