# Lika Tattoo Bot

Telegram-бот для тату-мастера с:

- каталогом примеров работ из `..\assets\portfolio`
- прайсом и контактами
- первыми `5` бесплатными генерациями для каждого пользователя
- платными пакетами генераций через Telegram Stars
- платежным меню для сервисных оплат через Telegram Payments
- портфолио-акцией, где клиент оплачивает только расходники
- готовым Robokassa-flow для `pay-interface` с `Receipt`, `ResultURL` и SQLite-учетом счетов
- генерацией эскизов через OpenAI Images API
- отдельным режимом `Prompt для ChatGPT`, который собирает prompt и открывает обычный ChatGPT
- локальной SQLite-базой

## Что уже работает

### Deep Links в Telegram

Бот поддерживает быстрые входы через `/start` с параметром:

- `/start booking` — сразу в заявку на запись
- `/myid` — показать свой Telegram ID для настройки `ADMIN_CHAT_ID`
- `/start generate` — сразу в генерацию эскиза
- `/start chatgpt` — сразу в сборку prompt для ChatGPT
- `/start deposit` — сразу в оплату и бронь
- `/start portfolio` — сразу в портфолио-акцию
- `/start examples` — сразу в примеры работ
- `/start contacts` — сразу в контакты мастера

### Пакеты генераций

Для каждого нового пользователя:

- первые `5` генераций выдаются бесплатно

Без отдельного merchant token:

- `50 XTR` -> `5` генераций
- `120 XTR` -> `15` генераций

Это цифровой товар, поэтому Telegram Stars подходят сразу.

### Предоплата сеанса

Для реальной предоплаты офлайн-сеанса в рублях бот умеет работать в двух режимах:

- через `PAYMENTS_PROVIDER_TOKEN` и встроенный Telegram invoice
- через Robokassa `pay-interface`

Если `PAYMENTS_PROVIDER_TOKEN` пустой и Robokassa не настроена, бот:

- показывает меню оплат
- объясняет, что для реальной оплаты сеанса нужен провайдерский токен

Если токен задан, бот умеет:

- принять обычную предоплату за сеанс
- принять портфолио-оплату, где клиент оплачивает только расходники
- запросить имя и телефон на этапе invoice
- обработать `/support` и `/terms` для платежного контура
- обработать `/paysupport` для вопросов по оплате
- отправить мастеру уведомление с типом оплаты и контактами клиента

Если Telegram invoice не подключен, но Robokassa настроена полностью, бот умеет:

- создать новый счет Robokassa с `InvId`
- сформировать `Receipt`
- выдать пользователю защищенную ссылку на оплату
- поднять локальный callback-сервер для `ResultURL`, `SuccessURL`, `FailURL`
- подтвердить оплату по подписи Robokassa
- записать платеж идемпотентно в SQLite
- отправить мастеру уведомление после callback

### Режим через ChatGPT

- команда `/chatgpt` и кнопка `🧠 Prompt для ChatGPT` не тратят баланс генераций
- бот собирает готовый prompt под генерацию эскиза и дает кнопку открытия `chatgpt.com`
- если у пользователя в ChatGPT доступна генерация изображений, он может продолжить уже там
- это полезно как fallback, когда API-генерация во встроенном режиме временно недоступна

## Установка

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Для проверок и разработки:

```powershell
pip install -r requirements-dev.txt
```

## Настройка

Файл `.env` уже создан.

Обязательно заполнить:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` — например `https://codex.sale/v1`, если используешь OpenAI-совместимый провайдер

Для реальной предоплаты офлайн-сеанса дополнительно заполнить:

- `PAYMENTS_PROVIDER_TOKEN`

Необязательно:

- `ADMIN_CHAT_ID`
- `TELEGRAM_PROXY_URL`
- `FREE_GENERATIONS_ON_START`
- `PORTFOLIO_PROMO_ENABLED`
- `PORTFOLIO_PROMO_RUB`
- `PORTFOLIO_PROMO_TITLE`
- `VK_URL`
- `VK_GROUP_SCREEN_NAME`
- `VK_GROUP_ID`
- `TELEGRAM_CHANNEL_URL`
- `WHATSAPP_URL`
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_CONSUMABLES_RANGE`
- `GOOGLE_SHEETS_BOOKING_RANGE`
- `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE`
- `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_PUBLISHED_CSV_URL`
- `YANDEX_DISK_LOCAL_PATH`
- `ROBOKASSA_MERCHANT_LOGIN`
- `ROBOKASSA_PASSWORD1`
- `ROBOKASSA_PASSWORD2`
- `ROBOKASSA_HASH_ALGORITHM`
- `ROBOKASSA_IS_TEST`
- `ROBOKASSA_RESULT_URL`
- `ROBOKASSA_SUCCESS_URL`
- `ROBOKASSA_SUCCESS_URL_METHOD`
- `ROBOKASSA_FAIL_URL`
- `ROBOKASSA_FAIL_URL_METHOD`
- `ROBOKASSA_BIND_HOST`
- `ROBOKASSA_BIND_PORT`

Если хочешь получать уведомления о новых заявках и оплатах в свой Telegram, открой бота и выполни `/myid`, затем вставь показанное число в `ADMIN_CHAT_ID`.

Если `api.telegram.org` напрямую не открывается, укажи локальный прокси, например:

```powershell
TELEGRAM_PROXY_URL=http://127.0.0.1:10808
```

Для синка публичного калькулятора и календаря с Google Sheets:

- `GOOGLE_SHEETS_SPREADSHEET_ID` — ID таблицы
- `GOOGLE_SHEETS_CONSUMABLES_RANGE` — диапазон листа расходников, например `Расходники!A:Z`
- `GOOGLE_SHEETS_BOOKING_RANGE` — диапазон листа записи, например `Запись!A:Z`
- `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE` или `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_PUBLISHED_CSV_URL` — безопасный fallback для расходников, если таблица опубликована как CSV
- `GOOGLE_CRM_SPREADSHEET_ID` — ID CRM-таблицы с заявками
- `GOOGLE_CRM_TITLE` — заголовок CRM-таблицы, по умолчанию `PPDSTR CRM`
- `GOOGLE_CRM_OWNER_EMAIL` — email, с которым нужно поделиться CRM-таблицей после создания

Для локального импорта портфолио из Яндекс.Диска можно задать:

- `YANDEX_DISK_LOCAL_PATH`

## Запуск

Проверка конфигурации:

```powershell
python main.py --check
```

Быстрый отчёт по заявкам:

```powershell
python main.py --booking-report
```

Обновить статус заявки:

```powershell
python main.py --booking-status 12 contacted
```

Создать CRM-таблицу Google Sheets:

```powershell
python main.py --crm-init --crm-owner-email your@email
```

Синкнуть заявки из SQLite в CRM:

```powershell
python main.py --crm-sync
```

Старт бота:

```powershell
python main.py
```

Если Robokassa настроена полностью, `python main.py` автоматически поднимет локальный HTTP-сервер callback-эндпоинтов на `ROBOKASSA_BIND_HOST:ROBOKASSA_BIND_PORT`.

Или через cmd:

```powershell
run_bot.cmd
```

## Quality Checks

```powershell
python main.py --check
python -m compileall main.py app tests
python -m ruff check .
python -m mypy main.py app tests
python -m pytest tests
python -m pip_audit -r requirements.txt
```

## Где лежат данные

- SQLite: `data\bot.db`
- сгенерированные эскизы: `data\generated`

## Что усилено в коде

- Платежи по Telegram Stars и предоплата обрабатываются идемпотентно по `telegram_charge_id` и `provider_charge_id`.
- Для сервисных оплат теперь хранятся тип оффера и его название, чтобы было видно, что оплатил клиент: обычную бронь или портфолио-акцию.
- Для Robokassa теперь хранятся счета `InvId`, `Receipt`, `Shp_*`, URL оплаты и callback-статус.
- Пополнение генераций и запись платежа теперь происходят в одной транзакции SQLite.
- Списание генераций защищено от ухода в отрицательный баланс.
- Конфиг валидирует критичные значения `.env`: URL, числовые пакеты, размер и качество изображения.
- Добавлен модуль `app/robokassa.py` для формирования подписи, `Receipt`, payment-link и проверки callback-подписей Robokassa по `pay-interface`.
- Добавлен модуль `app/robokassa_web.py` для `ResultURL`, `SuccessURL`, `FailURL` и ответа `OK{InvId}`.
- Self-check теперь печатает кириллицу без кракозябр.

## Важно

- Я не вставляю реальный приватный OpenAI-ключ или токен Telegram от себя, поэтому в `.env` оставлены плейсхолдеры.
- Пакеты генераций работают через Stars.
- Предоплата сеанса в рублях заработает только после добавления реального `PAYMENTS_PROVIDER_TOKEN` или полного рабочего набора `ROBOKASSA_*`.
- Портфолио-акция по оплате только расходников использует тот же платежный контур, что и обычная предоплата.
- API-генерация в боте и генерация в обычном ChatGPT — это два разных сценария: первый использует `OPENAI_API_KEY`, второй открывает внешний ChatGPT-чат и не расходует баланс бота.
