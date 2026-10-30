# Tinkoff Stock Monitor MVP

Минимальный, но рабочий MVP для мониторинга акций через FastAPI + HTML/CSS/Vanilla JS.

## Что реализовано

- 2 страницы: `login` и `dashboard`
- cookie-session авторизация с пользователем по умолчанию `admin/admin`
- live-обновление каждую секунду через SSE
- абстракция `PriceProvider`
- `TinkoffPriceProvider` и `MockPriceProvider`
- автоматический fallback в mock-режим, если токена нет или Tinkoff API недоступен
- независимый цикл мониторинга для каждой акции
- расчёты на `Decimal`
- unit-тесты для ключевой бизнес-логики и базового HTTP flow

## Структура

```text
stock_monitor_site/
├── .env.example
├── app.py
├── requirements.txt
├── README.md
├── static/
│   ├── app.js
│   └── styles.css
├── stock_monitor/
│   ├── __init__.py
│   ├── application.py
│   ├── auth.py
│   ├── config.py
│   ├── monitor.py
│   ├── providers.py
│   ├── schemas.py
│   └── utils.py
├── templates/
│   ├── dashboard.html
│   └── login.html
└── tests/
    ├── test_app.py
    └── test_logic.py
```

## Бизнес-логика

После запуска мониторинга все тикеры получают старт на ближайшую следующую границу окна `N` минут.

Для каждой акции независимо:

1. После старта на ближайшей округлённой границе времени начинается цикл мониторинга.
2. Внутри цикла непрерывно собираются `MIN`, `MAX`, `Изменение % = ((MAX - MIN) / MAX) * 100`.
3. После завершения каждого окна `N` минут рассчитываются:
   - `range = MAX - MIN`
   - `rollback_value = range * (rollback_percent / 100)`
   - `rollback_min = MIN + rollback_value`
   - `rollback_max = MAX - rollback_value`
4. Если цена касается уровня отката, только эта акция сбрасывается и ждёт ближайшую округлённую границу.
5. Если откат не задет, `MIN/MAX` продолжают накапливаться дальше, а rollback-уровни пересчитываются после каждого следующего окна.

## Быстрый старт

### Windows PowerShell

```powershell
cd F:\TinkSite\stock_monitor_site
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app:app --reload
```

Откройте `http://127.0.0.1:8000`

### Запуск тестов

```powershell
cd F:\TinkSite\stock_monitor_site
.\.venv\Scripts\Activate.ps1
pytest
```

## Переменные окружения

Смотрите `.env.example`.

Главные параметры:

- `APP_LOGIN`, `APP_PASSWORD`
- `TINKOFF_TOKEN`
- `FORCE_MOCK_PROVIDER=1` для принудительного mock-режима
- `DEFAULT_TICKERS`
- `DEFAULT_CHANGE_PERCENT`
- `DEFAULT_WINDOW_MINUTES`
- `DEFAULT_ROLLBACK_PERCENT`

## Как работает live-режим

- Frontend открывает `EventSource` на `/api/stream`
- Сервер отправляет полный snapshot состояния каждую секунду
- Таблица и верхняя панель обновляются без перезагрузки страницы

## Замечание по Tinkoff API

В реальном режиме используется официальный SDK `tinkoff-investments`: тикеры сначала резолвятся через `find_instrument`, затем последняя цена читается через `market_data.get_last_prices`.

Если SDK не установлен, токен не задан или API отвечает ошибкой, приложение автоматически переключается на `MockPriceProvider`.

Для реального режима установите SDK отдельно:

```powershell
pip install tinkoff-investments
```
