# Deployment Guide

Инструкция рассчитана на запуск проекта за 30 минут без правки кода.

## 1. Clone repo

```bash
git clone <repo-url> support-bot
cd support-bot
```

## 2. Local demo без `.env` или production через `.env`

### Для локального demo

Можно не создавать `.env` вообще.

```bash
docker compose up -d
```

По умолчанию включатся:

- `APP_ENV=local`
- `LLM_PROVIDER=mock`
- `MAX_MOCK_MODE=true`
- mock YooKassa
- `ADMIN_API_SECRET=demo-admin-secret`

### Для production или sandbox-интеграций

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Потом заполни реальные ключи.

## 3. Заполнить ключи, если нужен боевой режим

Минимальный набор:

- `APP_ENV=production`
- `WEBHOOK_BASE_URL=https://your-domain`
- `TELEGRAM_BOT_TOKEN`
- `MAX_API_TOKEN` или осознанно оставить `MAX_MOCK_MODE=true`
- `YOOKASSA_SHOP_ID`
- `YOOKASSA_SECRET_KEY`
- `YOOKASSA_RETURN_URL`
- `LLM_PROVIDER`
- provider-specific LLM credentials
- `ADMIN_API_SECRET`

Опционально:

- `TELEGRAM_PAYMENT_PROVIDER_TOKEN`
- `YOOKASSA_WEBHOOK_SECRET`
- `ADMIN_USER_IDS`

## 4. docker compose up -d

```bash
docker compose up -d
```

Поднимутся сервисы:

- `app`
- `postgres`
- `redis`
- `celery`
- `celery-beat`

## 5. alembic upgrade head

Контейнер `app` выполняет миграции автоматически при старте, но для ручной проверки можно выполнить:

```bash
docker compose exec app alembic upgrade head
```

## 6. Проверить healthcheck

```bash
docker compose ps
curl http://127.0.0.1:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

## 7. Проверить local demo

Открой:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/demo`

Через `POST /demo/events` можно пройти весь сценарий без Telegram/MAX/YooKassa.

Минимальная последовательность:

1. `/start`
2. `start:free`
3. `adult:yes`
4. `consent:privacy:accept`
5. `consent:offer:accept`
6. `consent:disclaimer:accept`
7. `checkin:no`
8. три текстовых сообщения
9. `pay:yookassa:month`
10. `pay:mock:confirm:*`

## 8. Проверить Telegram

Если используешь реальный Telegram:

1. Заполни `TELEGRAM_BOT_TOKEN`.
2. Заполни `WEBHOOK_BASE_URL`.
3. При необходимости задай `TELEGRAM_WEBHOOK_URL`.
4. Проверь, что доступен endpoint:

```text
https://your-domain/webhooks/telegram
```

Проверь руками:

- `/start`
- 18+
- три согласия
- check-in
- 3 preview ответа
- paywall

## 9. Проверить MAX

Если используешь реальный MAX:

1. Заполни `MAX_API_TOKEN`.
2. При необходимости задай `MAX_WEBHOOK_SECRET`.
3. Проверь webhook:

```text
https://your-domain/webhooks/max
```

Если ключей нет, оставь `MAX_MOCK_MODE=true` и используй `/demo/events`.

## 10. Проверить YooKassa payment

Если используешь реальную YooKassa:

1. Заполни `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `YOOKASSA_RETURN_URL`.
2. Настрой webhook:

```text
https://your-domain/webhooks/payments/yookassa
```

или:

```text
https://your-domain/webhooks/payments/yookassa?secret=YOUR_SECRET
```

3. Проверь:

- запись в `payments`
- активацию подписки
- `payment_method_id` у автопродляемых тарифов
- receipt, если включён `YOOKASSA_ENABLE_RECEIPTS=true`
- recurring списания

## 11. Проверить webhooks

Смотри:

```bash
docker compose logs -f app
```

Интересующие маршруты:

- `/webhooks/telegram`
- `/webhooks/max`
- `/webhooks/payments/yookassa`

## 12. Смотреть логи и аудит

```bash
docker compose logs -f app
docker compose logs -f celery
docker compose logs -f celery-beat
```

Admin API:

```bash
curl -H "X-Admin-Token: $ADMIN_TOKEN" "http://127.0.0.1:8000/admin/audit-events"
curl -H "X-Admin-Token: $ADMIN_TOKEN" "http://127.0.0.1:8000/admin/crisis-incidents"
curl -H "X-Admin-Token: $ADMIN_TOKEN" "http://127.0.0.1:8000/admin/deletion-requests"
```

Если задан свой `ADMIN_API_SECRET`, используй его вместо demo token.

## 13. Остановить проект

```bash
docker compose down
```

Удалить volumes:

```bash
docker compose down -v
```

## 14. Обновить проект

```bash
git pull
docker compose up -d --build
docker compose exec app alembic upgrade head
```

## Чек-лист приёмки

1. `/start`
2. onboarding
3. 18+
4. privacy consent
5. offer consent
6. disclaimer consent
7. check-in
8. preview 3 сообщения
9. тарифы
10. оплата
11. `/subscription`
12. отключение автопродления
13. смена тарифа
14. запрос возврата
15. удаление данных
16. crisis message
17. `/minute`
18. `/diary`
19. daily check-in
20. weekly summary

## Перед production

Нужно обязательно:

1. вставить реальные ключи
2. настроить Telegram webhook
3. настроить MAX webhook
4. настроить YooKassa webhook
5. проверить receipt
6. проверить recurring списания
7. проверить legal реквизиты
