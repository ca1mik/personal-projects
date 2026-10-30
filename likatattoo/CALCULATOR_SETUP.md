# CALCULATOR_SETUP.md

## Что сделано

- На главной странице работает калькулятор предварительного расчета.
- Он больше не выглядит как отдельная «вторая форма отправки».
- Его главная задача:
  - снизить страх по цене;
  - показать понятный диапазон;
  - объяснить, из чего складываются расходники;
  - передать результат в основную заявку.

## Где лежит логика

- UI и расчеты:
  - `site/client.js`
- Разметка блока:
  - `site/client.html`
- Стили калькулятора:
  - `site/client-theme.css`
- Данные расходников:
  - `site/data/consumables.json`
- Синхронизация из Google Sheets:
  - `site/scripts/sync_google_sheet_data.py`
- Note-based booking logic:
  - `bot/app/google_sheets_sync.py`

## Источник данных

- Spreadsheet URL:
  - `https://docs.google.com/spreadsheets/d/1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM/edit?gid=0#gid=0`
- Spreadsheet ID:
  - `1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM`
- Лист расходников:
  - `gid=0`
- Текущий способ подключения:
  - публичный CSV export Google Sheets

Команда обновления:

```bash
python site/scripts/sync_google_sheet_data.py --spreadsheet-url "https://docs.google.com/spreadsheets/d/1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM/edit?gid=0#gid=0" --allow-fallback
```

После sync данные сохраняются в:

- `site/data/consumables.json`

## Что учитывает калькулятор

- стиль;
- размер;
- место нанесения;
- цветность;
- сложность;
- есть ли готовый эскиз;
- комментарий;
- сценарий первой татуировки.

## Что показывает результат

- предварительный диапазон стоимости;
- примерную длительность сеанса;
- сгруппированный список расходников;
- итог по расходникам;
- кнопку:
  - `Добавить расчет в заявку`

## Как работает текущая логика

1. `site/client.js` загружает `site/data/consumables.json`.
2. Если JSON успешно пришел из актуального sync, в интерфейсе показывается статус `google-sheets-csv`.
3. Если источник недоступен, сайт не падает и использует локальный fallback.
4. Расчет собирает:
   - диапазон цены по стилю и коэффициентам;
   - примерное время;
   - расходники по группам;
   - итоговый минимум по расходникам.
5. Кнопка калькулятора не отправляет отдельную заявку.
   Она переносит расчет в основной блок заявки.

## Группы расходников в UI

Вместо сырого списка строк из таблицы сайт теперь показывает укрупненные группы:

- рабочее место в коворкинге;
- картриджи / иглы;
- краска / пигмент;
- перенос эскиза;
- подготовка места и защита;
- перчатки;
- заживляющая пленка и уход.

Это сделано специально, чтобы клиент видел понятную логику, а не внутреннюю кухню коворкинга.

## Что скрыто из публичного расчета

Из клиентского интерфейса убраны шумные и служебные позиции, которые мешали восприятию:

- аренда ящика с замком;
- обезбол;
- латексный коврик;
- подписанный держак, оставленный в школе.

Сейчас они фильтруются в `site/client.js` по `row_index` и дополнительным строковым проверкам.

Фактически скрытые строки:

- `row_index = 4`
- `row_index = 16`
- `row_index = 18`
- `row_index = 26`

## UX-состояния калькулятора

- `loading`
  - пока страница подтягивает данные;
- `success`
  - когда расходники пришли из Google Sheets CSV;
- `warning`
  - когда включен локальный fallback;
- `handoff`
  - когда расчет перенесен в заявку.

## Что влияет на цену

- выбранный стиль;
- размер;
- место нанесения;
- цветность;
- сложность;
- готовность эскиза;
- примерная длительность сеанса;
- минимальный порог по расходникам.

## Как калькулятор связан с заявкой

- расчет сохраняется в `state.calc`;
- короткая заявка живет в том же блоке, поэтому отдельная вторая анкета больше не нужна;
- при submit формы итоговый текст заявки включает:
  - стиль;
  - размер;
  - место;
  - цветность;
  - сложность;
  - наличие эскиза;
  - сценарий первой татуировки;
  - диапазон цены;
  - время;
  - итог по расходникам.
- Референсы и фото не грузятся в форму принудительно:
  - пользователь сразу видит подсказку, что их удобнее дослать в WhatsApp / Telegram / VK после открытия чата.

## Лист записи и notes

В проекте уже подготовлена правильная логика для листа записи:

- слот считается занятым по `note`, а не по значению ячейки;
- note-based проверка реализована в:
  - `bot/app/google_sheets_sync.py`

Важно:

- публичный CSV Google Sheets не отдает `note`;
- поэтому в публичной фронтенд-части live booking-check по notes сейчас не включен;
- для этого нужен server-side доступ через service account.

## Что нужно для live note-based booking

Нужен один из вариантов:

- `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE`
- `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`

Также нужны env:

- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_CONSUMABLES_RANGE`
- `GOOGLE_SHEETS_BOOKING_RANGE`

## Fallback

- если Google Sheets CSV временно недоступен:
  - остается предыдущий `site/data/consumables.json`;
  - калькулятор продолжает работать;
  - UI честно показывает warning-статус.

## Что важно помнить

- итог калькулятора всегда предварительный;
- финальная стоимость подтверждается после идеи, зоны и референсов;
- калькулятор помогает принять решение, а не заменяет консультацию;
- список расходников на сайте специально упрощен до понятного клиентского уровня:
  - рабочее место
  - картриджи
  - пигмент
  - перенос эскиза
  - подготовка, защита и уход

## Update 2026-06-06 - premium UI polish

- Calculator UI was rebalanced to feel client-facing instead of admin-like.
- Result cards now carry the main visual weight.
- Request form remains step 2 and chat buttons stay secondary until the draft is prepared.

## Update 2026-06-07 - live request handoff

- The request form is no longer frontend-only.
- Current flow:
  1. calculator builds the estimate in `state.calc`
  2. request form submits to `POST /api/booking-request`
  3. backend stores the lead in SQLite
  4. backend sends a Telegram manager notification
  5. backend syncs the lead into Google CRM Sheets
  6. frontend still reveals chat buttons as the continuation step
- Request API resolution:
  - local: `http://127.0.0.1:8080/api/booking-request`
  - production default: `${window.location.origin}/api/booking-request`
  - explicit override: `<body data-request-api-url="https://YOUR-PUBLIC-BOT-ENDPOINT/api/booking-request">`
- CRM spreadsheet now used for website leads:
  - `1avDDao4Q7rsO3ovM-g6MbkHt9gpTjgNCAzUZvj8HpU8`
- Confirmed sheets/columns:
  - `CRM Dashboard`
  - `CRM Leads`
  - `CRM Statuses`
  - lead headers include contact channel, idea, style/similar work, size, placement, price range, next step, notes and source
