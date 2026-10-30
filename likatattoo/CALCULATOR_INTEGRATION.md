# CALCULATOR_INTEGRATION.md

## Google Таблица
- Spreadsheet ID:
  - `1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM`
- Лист расходников:
  - `Цена расходников`
  - публичный CSV `gid=0`
- Лист записи:
  - `МАЙ`
  - публичный лист есть, но notes через CSV не доступны
- Способ подключения:
  - расходники: публичный CSV
  - запись по notes: Google Sheets API через service account
- Где лежат credentials:
  - в проекте не хранятся
  - ожидаются через env:
    - `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE`
    - `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`
- Какие env нужны:
  - `GOOGLE_SHEETS_SPREADSHEET_ID`
  - `GOOGLE_SHEETS_CONSUMABLES_RANGE`
  - `GOOGLE_SHEETS_BOOKING_RANGE`
  - `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE`
  - `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_SHEETS_PUBLISHED_CSV_URL`

## Структура листа расходников

Формально первый лист не является чистой таблицей с заголовками. Это свободная доска с текстовыми строками вроде:
- `Аренда коворкинга 180 рублей в час / 800 рублей в день`
- `Картриджи, 100 руб шт`
- `Пленка заживляющая 10х10см, 150р`

Поэтому парсер работает в двух режимах:
1. header-based, если есть нормальные колонки
2. board-style fallback, если лист собран свободным текстом

| Колонка / поле | Назначение | Обязательная |
|---|---|---|
| `name` | имя позиции расходника | да |
| `price` | цена позиции | да |
| `category` | категория расходника | нет |
| `unit` | единица измерения | нет |
| `base_qty` | базовое количество | нет |
| `notes` | комментарий/описание | нет |

## Логика калькулятора
- публичный JSON расходников генерируется в `site/data/consumables.json`
- frontend берёт данные в `site/client.js`
- если таблица недоступна, frontend использует локальный fallback
- базовая математика учитывает:
  - размер
  - длительность
  - количество цветных пигментов
  - сложность
  - отдельные группы расходников:
    - coworking
    - needle
    - transfer
    - film
    - gloves
    - caps
    - pigment
    - cleaning
    - care
- минимальная планка расходников:
  - `1600 ₽`

## Второй лист записи
- реальный лист:
  - `МАЙ`
- структура:
  - повторяющиеся недельные блоки
  - строки-заголовки:
    - `День недели:`
    - `Дата:`
    - `Время:`
  - колонки ресурсов:
    - `Кушетка`
    - `Холдер`
    - `Ширма`

### Как считается занятость

Главное правило:
- заполненность значения ячейки не считается главным источником правды
- главным источником считается `note`

Реализовано:
- функция `isSlotBookedByCellNote(cell): boolean`
- файл: `bot/app/google_sheets_sync.py`

Логика:
- если `note` есть и не пустой — слот занят
- если `note` пустой — слот свободен
- `formattedValue` учитывается только как визуальная подпись, не как факт занятости

### Важное ограничение
- публичный CSV и публичный HTML-вид Google Sheets **не отдают** `note`
- значит, без service account нельзя честно построить живую занятость по правилам проекта
- сейчас на сайте это отражено честно:
  - расходники работают от реальной таблицы
  - booking-note sync остаётся `unconfigured`, пока не даны credentials

## API endpoints
- публичных backend-endpoint'ов для сайта сейчас нет
- текущая схема статического сайта:
  - `python site/scripts/sync_google_sheet_data.py`
  - скрипт пишет JSON прямо в `site/data/`
- фактически используются файловые endpoints:
  - `/data/consumables.json`
  - `/data/booking-snapshot.json`

## Проверки
- расходники из реальной таблицы подтянуты успешно:
  - источник в JSON: `google-sheets-csv`
- booking-note logic покрыт тестами:
  - `bot/tests/test_google_sheets_sync.py`
- smoke сайта проходит и проверяет доступность JSON

## Ошибки и fallback
- если Google Sheets недоступен и передан `--allow-fallback`:
  - остаётся предыдущий `consumables.json`
  - остаётся предыдущий `booking-snapshot.json`
- если booking API не настроен:
  - используется `default_booking_snapshot(reason="unconfigured")`
- если структура первого листа без заголовков:
  - парсер переключается на извлечение цен из свободного текста
