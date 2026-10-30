# FINAL AUDIT

## 1. Статус проекта

`READY_WITH_LIMITATIONS`

Проект теперь можно запустить и проверить локально без `.env` и без внешних API. Для этого достаточно `docker compose up -d` или локального запуска FastAPI в demo/mock режиме. Production-ограничения остались только там, где нужны реальные внешние ключи и реальные webhook-и.

## 2. Найденные проблемы

- Локальный запуск раньше зависел от `.env`, внешних ключей и реальных платёжных/LLM интеграций.
- YooKassa без ключей падала, а не переходила в безопасный demo flow.
- Telegram paywall мог показывать `sendInvoice` fallback даже без provider token.
- Без миграций локальная SQLite-база не была готова к полноценному demo-сценарию.
- Документация была ориентирована в основном на production и не объясняла no-env local режим.
- `.env.example` выглядел как обязательный шаг даже для локального mock-прогона.

## 3. Список исправлений

- Добавлен полноценный local/demo режим без `.env`:
  - `LLM_PROVIDER=mock` по умолчанию
  - `MAX_MOCK_MODE=true` по умолчанию
  - mock YooKassa по умолчанию
- Добавлен `effective_admin_api_token` с demo-значением `demo-admin-secret` вне production.
- Добавлен auto-bootstrap схемы для локальной SQLite при startup.
- Реализован `POST /demo/events` для прохождения полного пользовательского флоу без Telegram и MAX.
- Реализован mock checkout и mock payment confirmation без внешней YooKassa.
- Исправлен paywall:
  - Telegram invoice fallback показывается только когда реально настроен provider token
  - mock checkout отдаёт кнопку `pay:mock:confirm:*`
- Обновлён `docker-compose.yml`:
  - больше не требует `.env`
  - все ключевые defaults встроены прямо в compose
- Обновлены `README.md`, `DEPLOYMENT.md`, `.env.example` под local/demo сценарий.
- Добавлены и обновлены тесты на:
  - `/demo`
  - no-env demo mode
  - mock YooKassa checkout/confirm
  - локальный acceptance flow

## 4. Что осталось ограничением из-за внешних сервисов

- `Telegram keys`
  - без реального `TELEGRAM_BOT_TOKEN` и при необходимости `TELEGRAM_PAYMENT_PROVIDER_TOKEN` нельзя подтвердить боевой Telegram webhook и реальный `sendInvoice` end-to-end
- `MAX keys`
  - без реального `MAX_API_TOKEN` нельзя подтвердить боевую доставку через MAX API
- `YooKassa shop/webhook`
  - без реальных `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL` и webhook нельзя подтвердить реальные списания, receipt и боевые recurring платежи
- `Реальные LLM API keys`
  - без внешних ключей нельзя подтвердить ответы реальных OpenAI / Anthropic / YandexGPT / GigaChat
- `Docker build local environment`
  - `docker build .` в этой среде упирается во внешний Docker Desktop engine `500 Internal Server Error`, это ограничение среды, а не репозитория

## 5. Как запустить

### Без `.env`, локально

```bash
docker compose up -d
```

Потом открыть:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/demo`

### С `.env`, для production/sandbox

```bash
cp .env.example .env
docker compose up -d
docker compose exec app alembic upgrade head
```

## 6. Как проверить

Через `POST /demo/events` или реальные мессенджеры пройти:

1. `/start`
2. onboarding
3. согласия
4. preview 3 сообщения
5. тарифы
6. оплата
7. подписка
8. LLM dialog
9. `/subscription`
10. отмена автопродления
11. смена тарифа
12. request refund
13. delete data
14. crisis message
15. `/minute`
16. `/diary`
17. check-in
18. weekly summary

## 7. Какие логи смотреть

- app logs

```bash
docker compose logs -f app
```

- celery logs

```bash
docker compose logs -f celery
docker compose logs -f celery-beat
```

- таблицы БД:
  - `payments`
  - `consents`
  - `crisis_incidents`
  - `deletion_requests`
  - `audit_events`

## 8. Что заказчик должен сделать перед production

- вставить реальные ключи
- настроить Telegram webhook
- настроить MAX webhook
- настроить YooKassa webhook
- проверить receipt
- проверить рекуррентные списания
- проверить legal реквизиты

## 9. Финальная самопроверка

Успешно выполнено:

- `ruff check .`
- `black --check .`
- `mypy .`
- `pytest`
- `docker compose config`
- `alembic upgrade head`
- локальный demo/mock прогон через FastAPI `TestClient`

Не подтверждено из-за внешней среды:

- `docker build .`
