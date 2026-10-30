# QA_REPORT.md

## Команды

В проекте нет `package.json`, поэтому стандартные `npm install / npm run build / npm run lint / npm run test` здесь неприменимы.
Проверки выполняются реальными командами этого репозитория:

```bash
node --check site/client.js
python site/scripts/smoke_check.py
python site/scripts/build_reg_ru_bundle.py
python bot/main.py --check
python -m ruff check bot
python -m compileall bot/main.py bot/app bot/tests
python -m pytest bot/tests
python site/scripts/sync_portfolio.py --source "F:\Yandex.Disk\ppdstr"
python site/scripts/sync_google_sheet_data.py --spreadsheet-url "https://docs.google.com/spreadsheets/d/1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM/edit?gid=0#gid=0" --allow-fallback
```

## Результаты

- Build:
  - `python site/scripts/build_reg_ru_bundle.py` — успешно
- JS syntax:
  - `node --check site/client.js` — успешно
- Smoke:
  - `python site/scripts/smoke_check.py` — успешно
- Bot self-check:
  - `python bot/main.py --check` — успешно
- Lint:
  - `python -m ruff check bot` — успешно
- Compile:
  - `python -m compileall bot/main.py bot/app bot/tests` — успешно
- Tests:
  - `python -m pytest bot/tests` — `40 passed`

## Проверенные сценарии

- Главная открывается локально.
- `/works` открывается локально.
- Юридические страницы `/offer`, `/payment`, `/privacy` отдаются без ошибок.
- Hero содержит 4 визуальных карточки работ и не содержит `character-arm-01`.
- Блок процесса отдает:
  - `session-long-01.mov`
  - `prep-process-01.mov`
- Калькулятор собирает grouped breakdown по расходникам.
- Кнопка калькулятора переносит расчет в заявку, а не имитирует отдельную отправку.
- После submit формы появляются messenger-actions и preview текста.
- Портфолио-манифест и consumables JSON читаются публично.
- В hero и trust явно видны медицинское образование и стерильность.
- В портфолио есть отдельный фильтр `Первая татуировка`.
- В карточках работ и модалке есть явный путь `Хочу похожую`.
- В футере и на `/works` есть ссылки на Яндекс Карты и 2ГИС.
- Расчет и заявка теперь находятся в одном блоке, а не в отдельных разорванных секциях.

## Что было найдено и исправлено

- Hero был слишком узкий визуально и перегружен мелкими вертикальными кадрами.
  - Исправлено: коллаж стал шире, сокращен до 4 кадров.
- В hero и в портфолио продолжала светиться нежелательная работа `character-arm-01`.
  - Исправлено: работа скрыта из публичной выдачи.
- Блок стерильности и процесса выглядел слишком статично.
  - Исправлено: восстановлены локальные видео `session-long-01.mov` и `prep-process-01.mov`.
- Native dropdown на тёмной теме открывался белым и плохо читался.
  - Исправлено: добавлены dark-select стили, `color-scheme: dark`, цвета для `option`.
- Breakdown расходников показывал мусор из Google Sheets.
  - Исправлено: скрыты служебные/спорные позиции, добавлена группировка по понятным блокам.
- Калькулятор выглядел как вторая форма отправки.
  - Исправлено: CTA переименован в `Заполнить заявку этим расчетом`.
- Блок заявки был перегружен постоянным textarea и несколькими каналами сразу.
  - Исправлено: один главный submit, compact actions после submit, preview спрятан в disclosure.
- Главный CTA на разных экранах был не до конца выровнен по тексту.
  - Исправлено: основной CTA приведен к `Получить расчет и записаться`.
- В форме согласия не хватало прямой ссылки на оферту.
  - Исправлено: consent теперь ссылается и на политику, и на оферту.
- В карточках работ не хватало явного действия и признака, что это кликабельный путь в заявку.
  - Исправлено: добавлен CTA `Хочу похожую` и параметр `Сеанс`.
- Новые фото в папке Яндекс.Диска не попадали на сайт без ручного редактирования JSON.
  - Исправлено: `sync_portfolio.py` теперь автоматически подхватывает новые изображения и дописывает библиотеку.
- Самые сильные новые работы не выводились в первый экран и верх портфолио.
  - Исправлено: в приоритет вручную поставлены дракон на предплечье и птица со стрелой.
- Расчет и заявка были разорваны на несколько визуально спорных блоков.
  - Исправлено: калькулятор и заявка собраны в один секционный flow `Расчет и запись`.
- Процесс и студия попадали в общую сетку работ, будто это тату-карточки.
  - Исправлено: публичная сетка теперь показывает только `collection === portfolio`.

Дополнительно в этом проходе:

- `sync_portfolio.py` получил поддержку `.heic` / `.heif`, чтобы новые айфоновские кадры не выпадали из автоматического обновления сайта.
- В trust-блок подключен отдельный портрет мастера:
  - source: `IMG_0963.heic`
  - public image: `/images/master/master-portrait-01.webp`
- В `media_sync.process_videos` закреплены и автоматически обновляются:
  - `/images/process/session-long-01.mov`
  - `/images/process/prep-process-01.mov`
- `smoke_check.py` теперь отдельно проверяет эти бинарные ассеты, чтобы будущий sync не сносил видео молча.
- На `/works` скрыт пустой фильтр `Процесс`, который раньше создавал ложное ожидание отдельной выдачи в сетке.
- Базовая HTML-заглушка process-блока приведена к тем же видео, что и JS-рендер:
  - `session-long-01.mov`
  - `prep-process-01.mov`

## Что осталось не сделано

- Live `https://www.ppdstr.ru/` по состоянию на `2026-06-05` все еще не обновлен новым bundle.
- Live `/works` на домене пока не опубликован, пока не загрузить новый архив на REG.RU.
- Форма заявки все еще не пишет данные на собственный backend и не загружает файлы server-side.
- Note-based booking logic реализована в коде, но live credentials для Google Sheets API не подключены.
- Автосинхронизация обновляет проект и deploy-бандл, но не может сама загрузить файлы в REG.RU без отдельного шага публикации.
- Реальное отдельное фото мастера из последнего референса пользователя пока не сохранено отдельным локальным JPG/PNG в проекте, поэтому trust-блок все еще использует текущий локальный fallback-кадр.

## Критичные проблемы

- Критичных ошибок сборки или smoke-check после текущего pass не обнаружено.
- Главный внешний blocker — не код, а отсутствие публикации свежего bundle в `public_html` на хостинге.

## Mobile-проверка

- Sticky CTA остается предусмотренным CSS.
- Hero упрощен и лучше читается за счет более широкого правого коллажа.
- Расчет и заявка собраны в одну секцию, поэтому mobile-path стал короче и понятнее.
- Поле preview заявки спрятано в disclosure, поэтому mobile не раздувается лишним textarea.
- Карточки расходников и формы остаются одноколоночными на small screens.

## Проверка CTA

- Основной CTA: `Получить расчет и записаться`
- Вторичный CTA: `Смотреть работы`
- Калькуляторный CTA: `Заполнить заявку этим расчетом`
- CTA после submit: WhatsApp / Telegram / VK появляются только после сборки текста
- В футере контакты дополнены картографическими ссылками без лишнего дублирования
- Запрос больше не разбит на отдельную секцию ниже калькулятора: расчет и отправка теперь рядом.

## Проверка формы заявки

- Есть поля имени, контакта, стиля, размера, места, цветности, идеи, референсов, комментария и consent.
- Есть честный fallback по референсам: сами фото лучше дослать в мессенджер после submit.
- `reportValidity()` используется.
- После submit собирается единый текст заявки.
- Текст можно скопировать и отправить в выбранный канал.

## Проверка калькулятора

- Источник: `site/data/consumables.json`
- Source status показывает `google-sheets-csv` или fallback.
- Breakdown теперь группированный:
  - рабочее место
  - картриджи
  - пигмент
  - перенос эскиза
  - подготовка места
  - перчатки
  - заживляющая пленка и уход
- Служебные и шумные позиции скрыты из UI.
- Блок `Расчет и запись` больше не выглядит как три отдельные формы:
  - оставлен один сценарий расчета
  - короткая заявка встроена в тот же compose-блок
  - референсы вынесены в понятную подсказку `дошлите в личку`
- Дополнительный visual pass:
  - убрано пустое растягивание левой формы
  - стоимость вынесена в широкую hero-card внутри расчета
  - действия после submit собраны в более чистый блок выбора чата

## Проверка портфолио

- Портфолио встроено на сайт.
- Главная показывает curated карточки.
- `/works` готов как отдельная страница со всеми работами.
- `character-arm-01` скрыт из публичного списка.
- Добавлены две сильные приоритетные работы в hero и верх галереи.
- Автодобавление новых фото в библиотеку работает через sync-скрипт и watcher.
- Процесс и студия больше не попадают в work-grid как будто это портфолио-работы.

## Проверка юридических ссылок

- `/offer` — доступна
- `/payment` — доступна
- `/privacy` — доступна
- ссылки в форме на политику ведут на рабочую страницу

## Технические проверки

- `npm run build`:
  - not applicable
- `npm run lint`:
  - not applicable
- `npm test`:
  - not applicable
- `python site/scripts/build_reg_ru_bundle.py`:
  - passed
- `python bot/main.py --check`:
  - passed
- `python -m pytest tests`:
  - passed
- `node --check site/client.js`:
  - passed
- `python site/scripts/smoke_check.py`:
  - passed
- console errors:
  - не проверялись через полноценный браузерный devtools-run в этой сессии
- broken links:
  - smoke-check critical public routes passed
- broken images:
  - прямых битых путей в актуальных маршрутах не выявлено

## Финальный чеклист

- [x] Первый экран понятен за 5 секунд
- [x] Есть реальные работы/портфолио
- [x] Один основной CTA
- [x] Форма заявки работает
- [x] Калькулятор работает или есть понятный fallback
- [x] Sticky CTA на mobile работает
- [x] Бот не конкурирует с записью
- [x] Тексты короткие и человеческие
- [x] Нет служебных фраз в обновленных проблемных блоках
- [x] Mobile не перегружен
- [x] Юридические ссылки работают
- [x] Нет ошибок сборки
- [x] Нет критичных ошибок smoke-check
- [x] Сайт больше не выглядит как текстовый прототип в ключевых экранах

## CRM / Google Sheets

- Код для CRM в Google Sheets реализован:
  - `bot/app/google_crm.py`
  - `python main.py --crm-init`
  - `python main.py --crm-sync`
- CRM шаблон в коде расширен до более удобной воронки:
  - контакт
  - канал связи
  - идея / запрос
  - стиль / похожая работа
  - диапазон цены
  - дата сеанса
  - предоплата
  - последнее касание
  - следующий шаг
  - заметки
- Таблица пока не создана автоматически из-за Google-side permission blocker.
- Точное действие для разблокировки:
  - открыть таблицу `1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM`
  - выдать `Editor` сервисному аккаунту
  - `ppdstr@majestic-bloom-498601-n8.iam.gserviceaccount.com`

## Update 2026-06-06 - Premium polish pass

### What was improved
- stronger hero collage and typography rhythm
- featured portfolio hierarchy and richer hover states
- cleaner trust/process/pricing/request styling
- clearer FAQ interactions and cleaner footer layout

### Extra checks
- `node --check site/client.js` - passed
- `python site/scripts/smoke_check.py` - passed
- `python site/scripts/build_reg_ru_bundle.py` - passed
- `npm run build` - not applicable, no `package.json` in this repo
- `npm run lint` - not applicable, no `package.json` in this repo
- `npm run test` - not applicable, no `package.json` in this repo

## Update 2026-06-07 - Rollback QA pass

### What was checked
- Hero, portfolio grid, trust block, sterility block, footer and the `Расчет и запись` section against the approved screenshots.
- Submit flow of the request form:
  - valid form submit
  - draft text generation
  - post-submit reveal of chat actions
  - WhatsApp link with composed text
  - manual fallback through `Скопировать текст`

### What was fixed
- Removed the last over-polished visual layer that broke the approved composition.
- Restored the 2x2 hero collage and regular 4-column portfolio layout.
- Restored the cat gif in the estimate card by stopping runtime removal in JS.
- Simplified footer back to a 3-column layout and disabled injected footer navigation.
- Removed process-image overlay captions so the sterility block matches the cleaner visual baseline.

### Current request flow status
- OK: form validation, draft generation, success/warning status, post-submit chat reveal
- OK: WhatsApp opens with prepared text
- Acceptable fallback: Telegram and VK open as follow-up channels; if auto-paste is not available, the prepared text can be copied manually

### Commands rerun
- `node --check site/client.js` - passed
- `python site/scripts/smoke_check.py` - passed
- `python site/scripts/build_reg_ru_bundle.py` - passed

## Update 2026-06-07 - CRM and website form verification

### Extra commands
- `python bot/main.py --check` - passed
- `python bot/main.py --crm-sync` - passed
- `python -m pytest bot/tests` - `41 passed`
- `python -m ruff check bot` - passed

### What was verified
- Google CRM spreadsheet is writable by the service account.
- CRM sheets exist:
  - `CRM Dashboard`
  - `CRM Leads`
  - `CRM Statuses`
- Website booking endpoint works end-to-end:
  - `POST /api/booking-request` -> `201`
  - SQLite latest row stored with `source=website-form`
  - backend reported `crm_synced: true`
  - follow-up `python main.py --crm-sync` reported `Lead rows synced: 2`

### Residual caveat
- The production site still needs a public API URL for the booking endpoint unless the domain serves `/api/booking-request` from the same origin.
- The site now supports that explicitly via `data-request-api-url` on `<body>`.


## Update 2026-06-07 - Fast request flow verification

### What was re-checked
- website submit -> SQLite
- website submit -> Google CRM sync
- frontend request state after successful API response
- local API health endpoint

### What was fixed
- website calc payload now sends human-readable labels for style, size, placement, color and complexity
- `/api/booking-request` no longer waits for Telegram/CRM before returning to the browser
- frontend now treats `crm_pending` as a healthy submit state instead of a false warning

### Verified end-to-end
- local POST to `/api/booking-request` returned `201`
- new booking request `#5` was saved in SQLite
- `python bot/main.py --crm-sync` synced `5` lead rows into Google CRM spreadsheet `1avDDao4Q7rsO3ovM-g6MbkHt9gpTjgNCAzUZvj8HpU8`

### Commands re-run
```bash
node --check site/client.js
python -m ruff check bot
python -m pytest bot/tests
python site/scripts/smoke_check.py
python bot/main.py --crm-sync
```

## Update 2026-06-07 - Request flow simplification
- ?????????? ????? ??????? ? ???????????? ????????-??????.
- ???????? ????? ???????? flow ??????: `??????? -> ???? -> ???????? -> ????? ????`.
- Backend-????????: `POST /api/booking-request` ?????????? `201`, ?????? ??????????? ? SQLite ? ????? ???????????????? ? Google CRM.
- `python bot/main.py --crm-sync` -> `Lead rows synced: 7`.

## Update 2026-06-07 - Baseline rollback and live request verification

### What was checked
- The user-approved baseline layout from the screenshots was kept in place.
- The estimate card still uses the cat GIF instead of a static image.
- Frontend request labels, work summaries and process captions were checked after rollback.
- The website request flow was tested again all the way to Google CRM.

### What was fixed
- Removed the remaining broken `????` frontend strings from `site/client.js`.
- Restored readable summaries for:
  - selected work
  - calculated price range
  - process video captions
  - footer helper text

### Verified end-to-end
- `POST /api/booking-request` -> `201`
- new request `#9` was accepted by the backend
- `python main.py --crm-sync` -> `Lead rows synced: 9`

### Current UX state
- Before submit, chat buttons are hidden.
- After a successful submit, the user sees channel actions.
- WhatsApp gets the prepared text payload.
- Telegram and VK remain follow-up channels, with `Copy text` as fallback.

## Update 2026-06-08 - Full site evaluation with new reviews

### What was checked
- Hero clarity and first-screen trust signal
- Portfolio cards, filters and gallery CTA
- Trust section and review section
- Sterility media block
- Calculator -> request form chain
- API health and real request submit
- Google CRM sync after submit
- Media integrity for review images and master portrait

### What was fixed
- Re-synced local portfolio media so missing review/master assets are present again.
- Added and kept the new reviews directly on the site.
- Replaced the most internal-sounding helper copy in the portfolio/trust notes with client-facing text.

### Verified end-to-end
- `python site/scripts/smoke_check.py` - passed
- `node --check site/client.js` - passed
- `python -m pytest bot/tests` - `41 passed`
- `python -m ruff check bot` - passed
- `python site/scripts/build_reg_ru_bundle.py` - passed
- local `POST /api/booking-request` -> `201`
- `python bot/main.py --crm-sync` -> `Lead rows synced: 12`

### Current strongest points
- Hero clearly communicates tattoo service in Kazan
- Portfolio is real, visible and filterable on-site
- Reviews now strengthen trust beyond portfolio alone
- Request flow is much clearer than before and reaches CRM

### Main remaining improvements
- Add a true public API URL for `/api/booking-request` on the live domain
- Add a separate healed-work block with 2-4 real healed examples
- Replace Gmail with confirmed domain mail if available
- Add 2-3 more verified reviews with matching photos
- Add one stronger photo of the master that feels less casual than the current crop

## Update 2026-06-08 - Full final pass before recommendations

### What was checked
- Hero clarity and first-screen conversion path
- Portfolio cards, filters and gallery CTA
- Trust section, review section and sterility block
- Calculator -> request form -> chat choice flow
- Local API health and CRM sync
- Media integrity for review photos and master portrait

### What was fixed
- Re-verified and kept the new reviews directly on the site.
- Confirmed missing portfolio/master assets are restored after local sync.
- Reconfirmed that the request flow still reaches SQLite and Google CRM after the latest visual rollbacks.

### Commands re-run
```bash
python site/scripts/smoke_check.py
node --check site/client.js
python -m pytest bot/tests
python -m ruff check bot
python bot/main.py --crm-sync
```

### Results
- Smoke check: passed
- Frontend syntax check: passed
- Tests: `41 passed`
- Ruff: passed
- Google CRM sync: `Lead rows synced: 12`

### Current verdict
- The site is already strong visually and no longer looks like a draft prototype.
- The main user path works: works are visible, trust is understandable, estimate is clear enough, request is captured, and leads reach CRM.
- The main production gap is still the public backend URL for `/api/booking-request` on the live hosted domain.

## Update 2026-06-09 - Operational launch check

### What was checked
- Local public site availability
- Local bot/API availability
- Bot configuration readiness
- Static deploy bundle presence for REG.RU

### Commands re-run
```bash
python site/scripts/smoke_check.py
cd bot && .venv\Scripts\python.exe main.py --check
```

### Runtime status
- Local site started on `http://127.0.0.1:8820/`
- Local bot/API started from `bot\.venv\Scripts\python.exe main.py`
- `http://127.0.0.1:8080/robokassa/health` -> `200`
- `http://127.0.0.1:8820/` -> `200`
- `http://127.0.0.1:8820/works` -> `200`

### Deploy note
- REG.RU shared hosting should receive only the static site bundle:
  - `deploy/reg-ru/ppdstr.ru-upload.zip`
- The bot/API process is separate and should stay on the local PC or move to a VPS/public backend host.

### Follow-up runtime fix
- During a live request-chain recheck, request `#13` reached the local API successfully, but manual CRM sync initially failed because `google-auth` was missing in `bot\.venv`.
- Installed the missing dependency from `bot/requirements.txt`, restarted the bot process, rechecked Telegram API, and re-ran CRM sync successfully.

### Final runtime confirmation
- `http://127.0.0.1:8080/robokassa/health` -> `200`
- Telegram API `getMe` -> `ppdstr_bot`
- `python bot/main.py --crm-sync` -> `Lead rows synced: 13`

## Update 2026-06-09 - full funnel verification

### Verified locally
- `http://127.0.0.1:8820/` -> `200`
- `http://127.0.0.1:8820/works` -> `200`
- `http://127.0.0.1:8820/offer` -> `200`
- `http://127.0.0.1:8820/payment` -> `200`
- `http://127.0.0.1:8820/privacy` -> `200`
- `http://127.0.0.1:8080/robokassa/health` -> `200`

### Request pipeline verification
- Website request `#15` returned `201 Created`
- `python bot/main.py --crm-sync` -> `Lead rows synced: 15`
- Verified in SQLite that the latest website request keeps the pre-order labels:
  - `style_label`
  - `size_label`
  - `placement_label`
  - `color_label`
  - `complexity_label`
  - `calc_price_range`
  - `hours_label`
  - `selected_work_title`

### Reviews
- The two new review texts are already present in the review block on the site.
- Exact attached review photos from chat are still not imported into `site/images/reviews/`, because no local file path was provided in the workspace.
- To use the same two images from chat directly on the site, they should be added locally first.

### Highest-priority next improvements
- Add 2-4 healed examples near the review block.
- Replace the current trust image with a stronger master portrait or a cleaner master-at-work crop.
- Add 2-3 more review cards with real healed / color examples.
- Publish a stable public backend URL for `/api/booking-request`, so the REG.RU site writes directly into CRM and manager notifications.
