# Robokassa Readiness

Дата проверки: `2026-06-05`

## Что уже закрыто в коде

- На клиентском сайте есть публичный блок `Оплата и документы`.
- Добавлены публичные страницы:
  - `site/offer.html`
  - `site/payment.html`
  - `site/privacy.html`
- В футере сайта публично показаны:
  - телефон `+7 (965) 606-64-55`
  - e-mail `levkaldin19@gmail.com`
  - ИНН `164808067332`
- На публичных страницах заполнены:
  - получатель оплаты: `Калдин Лев Владимирович`
  - исполнитель услуг: `Муфтахуддинова Анжелика Расуловна`
  - статус получателя оплаты: `плательщик налога на профессиональный доход (самозанятый)`
  - `ОГРНИП / ОГРН`: `не применяется`
  - адрес приема: `Казань, ул. Пушкина, 52, школа тату "Киви" (коворкинг, по записи)`
- Плейсхолдеры в `offer/payment/privacy/client` для карт и юридических полей заменены на рабочие данные.
- Контактные ссылки обновлены под реальный номер для `WhatsApp`.
- В боте реализован Robokassa-flow:
  - сборка payment-link для `pay-interface`
  - расчет `SignatureValue`
  - формирование `Receipt`
  - хранение счетов `InvId` в SQLite
  - локальный HTTP-слой для `ResultURL`, `SuccessURL` и `FailURL`
  - ответ `OK{InvId}` для `ResultURL`
  - идемпотентная фиксация оплаты в `deposits` и `payments`
  - уведомление мастеру после подтвержденного callback
- Локальные проверки пройдены:
  - `python -m pytest tests` -> `36 passed`
  - `python main.py --check`
  - `python -m ruff check .`

## Что теперь умеет бот

- Если задан `PAYMENTS_PROVIDER_TOKEN`, сервисные оплаты идут через встроенный Telegram invoice.
- Если `PAYMENTS_PROVIDER_TOKEN` пустой, но Robokassa настроена полностью, бот:
  - создает новый счет `InvId`
  - формирует `Receipt`
  - выдает защищенную ссылку Robokassa
  - принимает callback на `ResultURL`
  - записывает оплату в SQLite без дублей
  - отправляет уведомление мастеру

## Что еще нужно для фактического подключения

1. Рабочие секреты Robokassa:
   - `ROBOKASSA_MERCHANT_LOGIN`
   - `ROBOKASSA_PASSWORD1`
   - `ROBOKASSA_PASSWORD2`
2. Публичные callback URL:
   - `ROBOKASSA_RESULT_URL`
   - `ROBOKASSA_SUCCESS_URL`
   - `ROBOKASSA_FAIL_URL`
3. Публичный адрес сайта без ограничений доступа.
4. Подтверждение, что `WhatsApp` действительно привязан к номеру `+7 (965) 606-64-55`.

## Что заполнить в `bot/.env`

```env
ROBOKASSA_MERCHANT_LOGIN=
ROBOKASSA_PASSWORD1=
ROBOKASSA_PASSWORD2=
ROBOKASSA_HASH_ALGORITHM=MD5
ROBOKASSA_IS_TEST=true
ROBOKASSA_BIND_HOST=127.0.0.1
ROBOKASSA_BIND_PORT=8080
ROBOKASSA_RESULT_URL=https://YOUR-PUBLIC-HOST/robokassa/result
ROBOKASSA_SUCCESS_URL=https://YOUR-PUBLIC-HOST/robokassa/success
ROBOKASSA_SUCCESS_URL_METHOD=GET
ROBOKASSA_FAIL_URL=https://YOUR-PUBLIC-HOST/robokassa/fail
ROBOKASSA_FAIL_URL_METHOD=GET
```

Если бот запускается на этом компьютере, а наружу его открывает туннель или reverse proxy, `YOUR-PUBLIC-HOST` должен вести именно на HTTP-сервер бота, а не только на статический сайт.

## Временная публикация callback-URL с этого ПК

Есть готовый минимальный сценарий запуска без отдельного VPS:

1. Запустить бота на этом компьютере:
   - `run_tattoo_bot.cmd`
   - или `cd bot && python main.py`
2. Открыть временный публичный callback-хост:
   - `run_bot_public.cmd`
3. Взять хост из `bot-tunnel.out.log`.
4. Подставить его в `bot/.env` и в кабинете Robokassa:
   - `ROBOKASSA_RESULT_URL=https://PUBLIC-HOST/robokassa/result`
   - `ROBOKASSA_SUCCESS_URL=https://PUBLIC-HOST/robokassa/success`
   - `ROBOKASSA_FAIL_URL=https://PUBLIC-HOST/robokassa/fail`
5. Проверить:
   - `http://127.0.0.1:8080/robokassa/health`
   - `https://PUBLIC-HOST/robokassa/health`

Важно:

- `run_bot_public.cmd` не меняет секреты и не трогает `bot/.env`, он только открывает внешний туннель на локальный порт `8080`.
- `localhost.run` дает временный URL. Если соединение оборвалось, адрес может поменяться, и тогда его нужно заново перенести в `bot/.env` и в кабинет Robokassa.
- Для модерации и постоянной работы лучше перейти на нормальный домен и reverse proxy, а не оставаться на временном tunnel-URL.

## Статус по 5 требованиям Robokassa

### 1. Ресурс существует и публично доступен

- В коде сайт готов.
- Для финального статуса нужен публичный URL и доступ без авторизации.

### 2. Актуальный контент

- Описание услуг, прайс, запись, Telegram-бот и портфолио-акция на сайте уже есть.
- После публикации важно оставить только реальные способы связи и оплаты.

### 3. Есть оферта

- Финальная публичная версия добавлена: `site/offer.html`.
- В оферте разведены роли получателя оплаты и исполнителя услуг.

### 4. Есть контактные данные

- Телефон и e-mail уже подставлены на сайт.
- Каналы связи `VK`, `Telegram`, `WhatsApp` тоже выведены публично.

### 5. Есть реквизиты продавца

- ИНН уже подставлен.
- Получатель оплаты, статус и исполнитель услуг уже показаны на публичных страницах.

## Официальные страницы, на которые ориентируемся

- `https://robokassa.com/offers/help-with-connection.php`
  - Robokassa прямо пишет, что для подключения нужны работающий ресурс, актуальный контент, оферта, контакты и реквизиты.
- `https://robokassa.com/payments/instrumenty-oplaty/messendzher-boty/`
  - официальный сценарий приема оплат в ботах и мессенджерах.
- `https://docs.robokassa.ru/ru/pay-interface`
  - официальный формат `pay-interface`, подписи и параметры оплаты.
- `https://docs.robokassa.ru/ru/notifications-and-redirects`
  - официальный формат `ResultURL`/redirect и ответ `OK{InvId}`.
- `https://partner.robokassa.ru/Questionnaire`
  - анкета подключения магазина.

## Следующий минимальный пакет данных от владельца

Чтобы довести оплату до реально проверяемого прод-сценария, нужен только этот минимум:

- полный рабочий набор `ROBOKASSA_*`
- публичный URL для callback-эндпоинтов Robokassa
- доступ к хостингу / серверу, где живет `ppdstr.online`
- подтверждение по `WhatsApp` на этом же номере
