# Telegram + MAX бот поддержки для одиноких мам

Production-ready проект AI-бота эмоциональной поддержки для Telegram и MAX. Бот ведёт пользователя через `/start`, подтверждение `18+`, три обязательных согласия, бесплатное превью на 3 ответа, оплату, подписку, полноценный LLM-диалог, кризисный протокол, `/subscription`, `/minute`, `/diary`, daily check-in и weekly diary summary.

Сервис позиционируется как информационно-консультационный продукт и эмоциональная поддержка. Это не лечение, не психотерапия и не медицинская помощь.

## Что уже работает без `.env` и без внешних API

Проект можно поднять локально вообще без `.env` и без реальных ключей:

```bash
docker compose up -d
```

Что включается по умолчанию:

- `LLM_PROVIDER=mock`
- `MAX_MOCK_MODE=true`
- mock-режим YooKassa
- demo admin token: `demo-admin-secret`
- локальный сценарий через `POST /demo/events`

Это позволяет пройти почти весь пользовательский флоу без Telegram, MAX, YooKassa и внешнего LLM.

## Архитектура

- `src/services/` — workflow, оплаты, подписки, кризисный протокол, LLM, onboarding, уведомления.
- `src/repositories/` — доступ к БД по repository pattern.
- `src/services/workflow.py` — единый сценарий для Telegram и MAX.
- `src/bot/telegram/` и `src/bot/max/` — платформенные адаптеры.
- `src/api/` — FastAPI, webhooks, admin endpoints, demo endpoints.
- `src/scheduler/` — Celery worker, Celery Beat, scheduled jobs.
- `migrations/` — Alembic миграции.

Подход: Clean Architecture, DDD-lite, service layer, repository pattern.

## Стек

- Python 3.12
- FastAPI
- Aiogram 3.x
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Redis
- Celery / Celery Beat
- Docker / Docker Compose

## Быстрый старт

### Вариант 1. Локальный demo без `.env`

```bash
docker compose up -d
```

Потом открой:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/demo`

Для локального прогона сценариев используй `POST /demo/events`.

### Вариант 2. С реальными ключами

```bash
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

## Как пройти флоу без Telegram и MAX

Используй `POST /demo/events` из Swagger (`/docs`) или любым HTTP-клиентом.

Пример последовательности:

1. `{"platform_user_id":"demo-1","command":"/start"}`
2. `{"platform_user_id":"demo-1","action":"start:free"}`
3. `{"platform_user_id":"demo-1","action":"adult:yes"}`
4. `{"platform_user_id":"demo-1","action":"consent:privacy:accept"}`
5. `{"platform_user_id":"demo-1","action":"consent:offer:accept"}`
6. `{"platform_user_id":"demo-1","action":"consent:disclaimer:accept"}`
7. `{"platform_user_id":"demo-1","action":"checkin:no"}`
8. Три раза отправить `{"platform_user_id":"demo-1","text":"..."}`.
9. Нажать кнопку `pay:yookassa:*`.
10. Подтвердить mock-платёж кнопкой `pay:mock:confirm:*`.

После этого подписка активируется без внешнего платёжного API.

## Основной флоу

1. `/start`
2. приветствие и дисклеймер
3. подтверждение `18+`
4. privacy consent
5. offer consent
6. disclaimer consent
7. согласие на daily check-in
8. free preview на 3 ответа
9. paywall с тарифами
10. оплата
11. активация подписки
12. полноценный диалог с LLM

## Согласия

- До подтверждения `18+` диалог заблокирован.
- Без всех трёх обязательных согласий бот не отвечает как консультант.
- Согласия сохраняются в `consents` с `user_id`, версиями и timestamp.
- Все действия логируются в `audit_events`.

Версии документов задаются через:

- `LEGAL_DOC_VERSION`
- `PRIVACY_POLICY_VERSION`
- `OFFER_VERSION`
- `DISCLAIMER_VERSION`

## Free preview

- По умолчанию доступно 3 бесплатных ответа.
- Лимит хранится в `users.free_preview_messages_used`.
- Одноразовость хранится в `users.preview_exhausted` и `users.preview_completed_at`.
- После 3 ответа бот показывает тарифы.

## Подписки

Тарифы по ТЗ:

- `Неделя поддержки` — `390 ₽`, `7 дней`, без автопродления
- `Месяц рядом` — `990 ₽`, `30 дней`, с автопродлением
- `Квартал заботы` — `2490 ₽`, `90 дней`, с автопродлением

Хранится:

- `plan`
- `status`
- `started_at`
- `expires_at`
- `auto_renew`
- `payment_method_id`
- `cancelled_at`

Поддержано:

- `/subscription`
- отмена автопродления
- смена тарифа
- запрос возврата
- удаление данных

## Платежи

### По умолчанию без внешнего API

Если нет `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY`, включается mock checkout:

- checkout создаётся локально
- кнопка оплаты превращается в `Подтвердить демо-оплату`
- подписка активируется без реального платёжного провайдера
- recurring в локальном режиме тоже симулируется

### Реальная YooKassa

Поддержано:

- создание платежа
- webhook оплаты
- receipt для 54-ФЗ
- `provider_payment_id`
- `payment_method_id`
- recurring payments
- retry
- idempotency webhook

Webhook:

- `POST /webhooks/payments/yookassa`

### Telegram Payments fallback

Для Telegram доступен `sendInvoice`, если заполнен:

- `TELEGRAM_PAYMENT_PROVIDER_TOKEN`

Ограничение: этот fallback не сохраняет `payment_method_id`, поэтому не подходит для автопродления.

## Telegram

Используется webhook-режим, не polling.

- endpoint: `POST /webhooks/telegram`
- если `TELEGRAM_WEBHOOK_URL` пуст, URL собирается как `WEBHOOK_BASE_URL + /webhooks/telegram`
- webhook выставляется на startup

Поддержано:

- `/start`
- `/subscription`
- `/minute`
- `/diary`
- постоянная reply-клавиатура, которую можно снова открыть кнопкой клавиатуры у поля ввода
- bot commands menu с командами `/start`, `/subscription`, `/minute`, `/diary`
- inline кнопки
- Telegram invoice fallback
- обработка ошибок Telegram API

## MAX

Реализован отдельный адаптер в `src/bot/max/`.

Поддержано:

- webhook endpoint `POST /webhooks/max`
- приём сообщений
- отправка сообщений
- callback-кнопки
- оплата через ссылку YooKassa
- structured logging входящих событий

Если реальных ключей нет:

- включается `MAX_MOCK_MODE=true`
- broken code в runtime не остаётся
- workflow продолжает работать в полном объёме
- локально сценарии можно тестировать через `/demo/events`

## LLM

Поддержаны провайдеры:

- `mock`
- `openai`
- `anthropic`
- `yandexgpt`
- `gigachat`

Выбор через `LLM_PROVIDER`.

Используется:

- `prompts/system.md`
- `prompts/crisis.md`
- `prompts/onboarding.md`
- rolling window
- summary прошлых сессий
- история в `messages`
- summary в `conversations.summary`

Если внешний LLM недоступен, local/demo режим работает на `mock` provider.

## Кризисный протокол

Проверка выполняется до обычного LLM-ответа.

Детектируются:

- суицид
- самоповреждение
- насилие
- риск вреда ребёнку

Если кризис найден:

- обычный диалог останавливается
- создаётся запись в `crisis_incidents`
- админы уведомляются
- пользователю отправляется кризисное сообщение с номерами:
  - `112`
  - `8-800-2000-122`
  - `8-495-989-50-50`

## Дополнительные функции

- `/minute` — случайная короткая практика
- `/diary` — дневник благодарностей
- daily check-in по согласию пользователя
- weekly diary summary
- recurring renewals через Celery

## Scheduled jobs

Запускаются через `celery` и `celery-beat`.

Поддержано:

- продление подписок
- ежедневный check-in
- индивидуальное время check-in
- еженедельная сводка дневника

Логи:

- `docker compose logs -f celery`
- `docker compose logs -f celery-beat`

## Admin и логи

Admin endpoints:

- `GET /admin/audit-events`
- `GET /admin/crisis-incidents`
- `GET /admin/deletion-requests`

Заголовок:

- `X-Admin-Token: <token>`

Локально без `.env` используется:

- `X-Admin-Token: demo-admin-secret`

Где смотреть аудит:

- `docker compose logs -f app`
- таблицы `payments`, `consents`, `crisis_incidents`, `deletion_requests`, `audit_events`

## Юридические документы

Файлы:

- `legal/privacy_policy.md`
- `legal/offer.md`
- `legal/disclaimer.md`

В них учтены:

- 152-ФЗ
- 38-ФЗ
- 54-ФЗ
- формулировки `информационно-консультационные услуги`
- формулировки `эмоциональная поддержка`
- отказ от позиционирования как лечение, психотерапия и медицинская помощь
- хранение данных граждан РФ
- отсутствие маркетинговых рассылок без отдельного согласия
- рекомендация не указывать имена детей

## Приёмочные сценарии

1. `/start` -> 18+ -> privacy -> offer -> disclaimer -> check-in
2. три preview сообщения
3. paywall
4. оплата
5. `/subscription`
6. отмена автопродления
7. смена тарифа
8. запрос возврата
9. удаление данных
10. кризисное сообщение
11. `/minute`
12. `/diary`
13. daily check-in
14. weekly summary

## Ограничения

- Без реальных ключей невозможно подтвердить боевую доставку Telegram webhook.
- Без реальных ключей невозможно подтвердить боевую доставку MAX webhook.
- Без реальных ключей невозможно подтвердить реальный YooKassa receipt и реальные recurring списания.
- В demo-режиме уведомления админам идут в аудит и логи, но не в реальные мессенджеры.
- `docker build .` зависит от работоспособности локального Docker Engine.

## Полезные команды

```bash
docker compose up -d
docker compose ps
docker compose logs -f app
docker compose logs -f celery
docker compose exec app alembic upgrade head
pytest -q
ruff check .
```

Подробный пошаговый сценарий запуска — в [DEPLOYMENT.md](DEPLOYMENT.md).
