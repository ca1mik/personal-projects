# PROGRESS.md

## Контекст проекта

- Стек:
  - публичный сайт: `HTML + CSS + vanilla JS` в `site/`
  - sync-скрипты и служебная автоматизация: `Python`
  - бот и интеграции: `Python` в `bot/`
- Как запускать:
  - локальный сайт: `python site/scripts/serve_public_site.py --host 127.0.0.1 --port 8820`
  - smoke-check: `python site/scripts/smoke_check.py`
  - сборка shared-hosting bundle: `python site/scripts/build_reg_ru_bundle.py`
  - sync расходников: `python site/scripts/sync_google_sheet_data.py --spreadsheet-url "https://docs.google.com/spreadsheets/d/1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM/edit?gid=0#gid=0" --allow-fallback`
  - sync портфолио: `python site/scripts/sync_portfolio.py --source "F:\Yandex.Disk\ppdstr"`
- Как тестировать:
  - `node --check site/client.js`
  - `python site/scripts/smoke_check.py`
  - `python site/scripts/build_reg_ru_bundle.py`
  - `python bot/main.py --check`
  - `python -m ruff check bot`
  - `python -m compileall bot/main.py bot/app bot/tests`
  - `python -m pytest bot/tests`
- Где главная:
  - `site/client.html`
- Где стили:
  - `site/client-theme.css`
- Где компоненты:
  - секции и блоки собраны прямо в `site/client.html`
  - интерактив, калькулятор, фильтры, модалка, форма: `site/client.js`
- Где изображения:
  - `site/images/portfolio/`
  - `site/images/process/`
  - `site/images/master/`
  - `site/images/studio/`
- Где юридические страницы:
  - `site/offer.html`
  - `site/payment.html`
  - `site/privacy.html`

## Что делаем

- Полный редизайн по концепции `Premium Dark Trust`
- Встроенное портфолио на главной
- Новый hero
- Новая CTA-система
- Форма заявки
- Калькулятор
- Mobile-first
- Переписанные тексты
- QA

## Текущий статус

- Главная страница редизайна: готово
- Страница `/works`: готово
- Локальная галерея из `F:\Yandex.Disk\ppdstr`: готово
- Google Sheets sync для расходников: готово
- Архитектура note-based booking: готово, live credentials пока не подключены
- Bundle для REG.RU: готово
- Финальный UX cleanup pass: готово

## Update 2026-06-05 - UX cleanup pass

- Hero-коллаж расширен и сокращен до 4 сильных кадров.
- `character-arm-01` скрыт с публичного сайта.
- Блок стерильности переведен на autoplay video `studio-couch-01.mp4` + supporting frame.
- Исправлен dark-стиль native select/dropdown на Windows Chrome.
- Калькулятор больше не показывает мусорные позиции вроде ящика с замком, латексного коврика, держака и обезбола.
- Расходники теперь группируются в понятные блоки вместо сырой простыни.
- CTA калькулятора упрощен до `Добавить расчет в заявку`.
- Блок заявки упрощен: одна основная форма, messenger-actions появляются только после submit, preview текста спрятан в раскрывающийся блок.

## Update 2026-06-06 - QA hard pass

- Главный CTA выровнен по сайту до `Получить расчет и записаться`.
- В hero и trust явно добавлено `Медицинское образование`.
- В карточках работ появился отдельный CTA `Хочу похожую`.
- Для портфолио добавлен отдельный фильтр `Первая татуировка`.
- В модалке работы добавлен отдельный параметр `Сеанс`.
- В форме согласия теперь есть и политика, и оферта.
- В футере и на странице `/works` добавлены `Яндекс Карты` и `2ГИС`.
- В request-flow добавлена честная подсказка по референсам: фото лучше досылать в мессенджер после submit.

## Update 2026-06-06 - portfolio sync and priority pass

- `sync_portfolio.py` теперь автоматически добавляет новые фото из `F:\Yandex.Disk\ppdstr` в библиотеку портфолио.
- Автодобавление пропускает сырые `IMG_*.JPG`, чтобы не засорять сайт процессом и студийными дублями.
- Добавлен watcher `site/scripts/watch_portfolio_sync.py` и launcher `run_portfolio_sync_watch.cmd`.
- Вручную закреплены две сильные новые работы:
  - `graphic-forearm-dragon-01`
  - `graphic-leg-bird-01`
- Hero-коллаж и верх портфолио переставлены под самые сильные графические работы.

## Update 2026-06-06 - estimate and request merged

- Блоки расчета и заявки объединены в один поток `Расчет и запись`.
- Теперь путь выглядит так:
  - выбрать параметры
  - получить предварительный диапазон
  - подставить расчет в форму
  - сразу отправить заявку
- Процесс и студия больше не попадают в сетку работ как карточки `Хочу похожую`.
- Для process-блока восстановлены локальные видео:
  - `site/images/process/session-long-01.mov`
  - `site/images/process/prep-process-01.mov`
- Слот под фото мастера оставлен в trust-блоке, но реальный portrait-файл в рабочую папку проекта пока не сохранен отдельным JPG/PNG.

## Update 2026-06-06 - HEIC sync and master portrait

- `site/scripts/sync_portfolio.py` теперь умеет обрабатывать:
  - `.heic`
  - `.heif`
- Это важно для локальной папки `F:\Yandex.Disk\ppdstr`, потому что новые айфоновские кадры больше не нужно вручную конвертировать перед sync.
- В trust-блок заведён отдельный портрет мастера:
  - источник: `IMG_0963.heic`
  - публичный файл: `site/images/master/master-portrait-01.webp`
- В `site/data/portfolio-library.json` добавлен `media_sync.process_videos`, поэтому sync теперь сам обновляет:
  - `site/images/process/session-long-01.mov`
  - `site/images/process/prep-process-01.mov`
- На `/works` скрыт мёртвый фильтр `Процесс`, потому что process/studio теперь живут в отдельном trust/process-сценарии, а не в сетке тату-работ.

## Update 2026-06-06 - compact request flow

- Блок `Расчет и запись` схлопнут в один понятный сценарий:
  - слева параметры татуировки
  - справа ориентир по цене и расходникам
  - тут же короткая заявка без второго набора полей
- Из заявки убраны дубли:
  - стиль
  - размер
  - место
  - цветность
  - file-upload референсов
- Теперь в заявке остаются только:
  - имя
  - контакт
  - идея
  - одно поле с уточнениями
  - согласие с политикой и офертой
- В итоговом сообщении явно написано, что референсы можно дослать уже в личные сообщения после открытия чата.
- Список расходников схлопнут до клиентских групп:
  - рабочее место
  - картриджи
  - пигмент
  - перенос эскиза
  - подготовка, защита и уход

## Update 2026-06-06 - visual cleanup of estimate section

- Блок `Расчет и запись` дополнительно переработан визуально:
  - левая колонка больше не растягивается пустотой по высоте;
  - убрано лишнее поле комментария из калькулятора;
  - правый compose-блок разделён на две аккуратные панели;
  - карточка стоимости стала главным визуальным акцентом;
  - кнопки продолжения после submit собраны в компактный чат-блок;
  - кнопка отправки стала понятнее: `Собрать заявку и выбрать чат`.

## Update 2026-06-06 - Google CRM scaffold

- Добавлен модуль `bot/app/google_crm.py`:
  - создание CRM-таблицы Google Sheets;
  - fallback на CRM-вкладки внутри уже существующей таблицы;
  - листы:
    - `CRM Dashboard`
    - `CRM Leads`
    - `CRM Statuses`
  - синк заявок из `bot/data/bot.db`
- В `bot/main.py` добавлены команды:
  - `python main.py --crm-init`
  - `python main.py --crm-sync`
- В `bot/.env.example` и `bot/README.md` добавлены:
  - `GOOGLE_CRM_SPREADSHEET_ID`
  - `GOOGLE_CRM_TITLE`
  - `GOOGLE_CRM_OWNER_EMAIL`
- Текущий внешний блокер:
  - service account умеет читать таблицу, но не имеет прав на запись
  - для запуска CRM нужно расшарить таблицу `1F3I8gheqwtwBNiFl6kCnUD9Wt2PUE8L18rHo_6yVCtM`
  - на сервисный аккаунт `ppdstr@majestic-bloom-498601-n8.iam.gserviceaccount.com`
  - с ролью `Editor`

## Update 2026-06-06 - Request layout and CRM template pass

- Секция `Расчет и запись` переложена так, чтобы карточки результата жили прямо под параметрами расчета, а справа оставался один цельный compose-блок.
- Убрано ощущение "пустого столба" под селекторами и случайной тетрис-раскладки.
- Для Google CRM подготовлен более удобный шаблон колонок:
  - статус
  - контакт
  - канал связи
  - идея / запрос
  - стиль / похожая работа
  - размер
  - место
  - когда удобно
  - диапазон цены
  - дата сеанса
  - предоплата
  - последнее касание
  - следующий шаг
  - заметки
- Фактическое создание/обновление Google CRM по-прежнему блокируется правами Google (`403 PERMISSION_DENIED`).

## Update 2026-06-06 - Premium polish pass

- Hero upgraded to a more editorial collage with one dominant work, uneven supporting cards and a small meta caption.
- Typography tuned for dark-background readability: larger H1/H2 rhythm, stronger body contrast and less washed-out muted text.
- Portfolio cards upgraded with featured hierarchy, hover lift, zoom and a denser desktop grid.
- Trust and process blocks polished to feel less household and more editorial.
- Calculator and request flow refined into a cleaner two-step hierarchy with clearer visual priority.
- FAQ upgraded with single-open behavior, plus/minus state and lighter answers.
- Footer upgraded to a cleaner multi-column structure with explicit navigation.

## Update 2026-06-07 - Rolled back to the approved baseline

- Reverted the last premium-only visual layer back to the user-approved version from the screenshots.
- Hero collage returned to a cleaner 2x2 rhythm instead of the editorial uneven stack.
- Portfolio returned to a regular 4-card desktop grid without featured-width distortion.
- Trust and sterility sections were simplified back to the calmer composition the user approved.
- Footer was reduced back to the cleaner 3-column layout; the injected nav column is no longer used.
- The cat gif was restored inside the estimate card in `Расчет и запись`.
- Request flow logic was checked: channels stay hidden before submit, draft text is generated after valid submit, WhatsApp gets the composed text, Telegram/VK stay as follow-up channels.

## Update 2026-06-07 - Website form -> CRM -> Telegram

- Added a real website booking API flow:
  - `site/client.js` now posts form data to `/api/booking-request`
  - local fallback uses `http://127.0.0.1:8080/api/booking-request`
  - production can override this via `data-request-api-url` on `<body>`
- Added/used Google CRM spreadsheet:
  - `GOOGLE_CRM_SPREADSHEET_ID=1avDDao4Q7rsO3ovM-g6MbkHt9gpTjgNCAzUZvj8HpU8`
- Created / synced sheets in the shared spreadsheet:
  - `CRM Dashboard`
  - `CRM Leads`
  - `CRM Statuses`
- Extended website leads so they now persist richer metadata in SQLite:
  - `source`
  - `details_json`
- Verified end-to-end:
  - website booking endpoint returned `201`
  - request stored as `website-form`
  - CRM sync returned `crm_synced: true`
  - `python main.py --crm-sync` now reports `Lead rows synced: 2`
- Added a token fallback in `bot/app/google_crm.py` for service-account auth, because the default google-auth refresh path was failing locally on SSL handshake to `oauth2.googleapis.com`.


## Update 2026-06-07 - Fast website request flow and CRM delivery

- Fixed the website request payload so CRM rows receive readable tattoo parameters instead of raw fallback values.
- Website submit flow no longer blocks on Telegram or Google Sheets:
  - the form now gets a fast `201` response from `/api/booking-request`
  - Telegram notification and CRM sync run in the background
- Verified the full chain locally:
  - website request saved into `bot/data/bot.db`
  - request returned `201`
  - `python bot/main.py --crm-sync` synced `5` lead rows into Google CRM spreadsheet `1avDDao4Q7rsO3ovM-g6MbkHt9gpTjgNCAzUZvj8HpU8`
- Temporary local API runner was removed after the test pass; no extra debug files should remain in the repo.

## Update 2026-06-07 - Symbols fixed and request form shortened
- ??????? ???????????? ????? ? `site/client.js`: ?????? ?????????? ? ????????, ?????????, ????????, ?????? ? ???????? ?????.
- ???? ?????? ???????: ??????????? ?????? `???????`, `????` ? `????????`; `???` ? `???????????` ?????????? ? ?????????????? ?????????????? ????.
- Backend `booking-request` ?????? ????????? ?????? ??? ????? ? ??????????? `??? ?????` ??? CRM/?????????.
- ????????? POST ?????????????: ?????? `#7` ????????? ? ????? ?? Google CRM.

## Update 2026-06-07 - Baseline design restored and booking flow re-checked
- Kept the user-approved visual baseline from the screenshots instead of the heavier polish pass.
- Preserved the cat GIF in the estimate card and cleaned up the remaining broken frontend strings in `site/client.js`.
- Re-verified the website request flow after the rollback:
  - local `POST /api/booking-request` returned `201`
  - booking requests `#8` and `#9` were stored in SQLite
  - `python main.py --crm-sync` synced `9` lead rows into Google CRM
- Confirmed current behavior:
  - before submit, chat buttons stay hidden
  - after a successful submit, the site shows channel choices
  - WhatsApp receives the prepared request text
  - Telegram / VK remain follow-up channels, with `Copy text` as fallback

## Update 2026-06-08 - Full local pass with reviews and media integrity
- Re-checked the full local site after the latest rollback:
  - hero
  - portfolio
  - trust
  - reviews
  - sterility
  - calculator + request form
  - FAQ
  - footer
- Added the two new review texts into the on-site `Отзывы` section and kept them paired with real local tattoo photos already in the project.
- Cleaned up copy that still sounded too internal:
  - portfolio footer note
  - trust follow-up note card
- Re-synced local media from `F:\Yandex.Disk\ppdstr` and confirmed the missing files are restored:
  - `site/images/master/master-portrait-01.webp`
  - `site/images/portfolio/characters/characters-arm-cupid-01.webp`
  - `site/images/portfolio/lettering/lettering-leg-01.webp`
- Re-tested the full website request chain:
  - `POST /api/booking-request` -> `201`
  - new request `#12` stored successfully
  - `python bot/main.py --crm-sync` -> `Lead rows synced: 12`
- Re-ran checks:
  - `python site/scripts/smoke_check.py`
  - `node --check site/client.js`
  - `python -m pytest bot/tests` -> `41 passed`
  - `python -m ruff check bot`
  - `python site/scripts/build_reg_ru_bundle.py`

### Main conclusion
- Locally the site now has a complete trust chain: real works -> reviews -> calculator -> request form -> CRM.
- The biggest remaining production blocker is still the public API URL for `/api/booking-request` on the live hosted site.

## Update 2026-06-08 - Full UX and CRM verification pass
- Re-tested the site as a real funnel:
  - first screen
  - portfolio visibility
  - trust and reviews
  - sterility block
  - calculator -> request form
  - API handoff
  - Google CRM sync
- Kept the two new reviews on-site and paired them with real local portfolio photos already available in the project.
- Re-verified media integrity after portfolio sync:
  - `site/images/master/master-portrait-01.webp`
  - `site/images/portfolio/characters/characters-arm-cupid-01.webp`
  - `site/images/portfolio/lettering/lettering-leg-01.webp`
- Re-ran the full local checks:
  - `python site/scripts/smoke_check.py`
  - `node --check site/client.js`
  - `python -m pytest bot/tests`
  - `python -m ruff check bot`
  - `python bot/main.py --crm-sync`
- Confirmed the operational state:
  - local site assets return `200`
  - request flow still writes to SQLite
  - CRM sync still reports `Lead rows synced: 12`

## Update 2026-06-08 - Repo hygiene pass and live booking-form diagnosis

- Security cleanup:
  - Removed `open-claw-agent-487913-...json`, an orphaned service-account key from an unrelated Google Cloud project (referenced nowhere in the repo).
  - Moved the active `majestic-bloom-498601-n8-...json` key into `bot/secrets/` (gitignored) and updated `GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE` in `bot/.env`.
  - Added `bot/secrets/`, `deploy/caddy/storage/` (Caddy ACME account + private keys) and `docs/personal/` to `.gitignore`.
- Repo cleanup: removed `tmp_fixed_preview.txt`, `tmp_heic_scan/` (duplicate JPGs), stray file `89.124.111.103`; moved `fns_extract.pdf` / `npd_api.pdf` (personal tax docs, unrelated to the project) into `docs/personal/`.
- Fixed mojibake (double-encoded Cyrillic) in the "Временная публикация" section of `README.md`.
- Rebuilt the REG.RU bundle (`python site/scripts/build_reg_ru_bundle.py`) - now includes `/works` and all recent updates that the live site is still missing.
- **Diagnosed why the live booking form cannot work right now**: `https://ppdstr.ru/api/booking-request` returns `404` from REG.RU's shared-hosting `nginx` (confirmed via direct `curl`). Shared hosting only serves static files - it cannot run the bot's Python/aiohttp backend, so `client.js`'s same-origin POST to `/api/booking-request` has nowhere to land. No website lead can currently reach the bot/CRM.
- Also found the live DNS picture has flipped since 2026-06-05: `ppdstr.ru` now resolves to `31.31.197.13` and serves the site (`200 OK`), while `ppdstr.online` still points to `95.163.244.138` (`400 Bad Request`) - the opposite of what `docs/domain-deploy.md` assumed.
- Decision from the user: solve this with a permanent VPS (site + bot on one server/origin). Prepared the groundwork ahead of provisioning:
  - Updated `deploy/nginx/ppdstr.conf`: added missing locations for `/works`, `client-theme.css`, `data/`, `images/`, plus `location /api/` and `location /robokassa/` reverse-proxy blocks to `127.0.0.1:8080` (the bot's `ROBOKASSA_BIND_HOST`/`PORT`). With this, the frontend's existing same-origin fallback (`data-request-api-url=""`) works without any change.
  - Added `deploy/systemd/likatattoo-bot.service`, a template unit to run `python main.py` (starts Telegram polling + booking API together) persistently on the VPS.
  - Expanded `docs/domain-deploy.md` with a "Бот и API на VPS" section (step-by-step) and flagged the canonical-domain mismatch that needs a decision before the nginx redirect is enabled.
- Re-ran local checks after all changes: `python bot/main.py --check`, `python -m ruff check bot`, `python -m pytest bot/tests` (41 passed), `python site/scripts/smoke_check.py` - all green.

## Update 2026-06-09 - full funnel verification

- Re-checked the full local user path:
  - first screen
  - portfolio
  - trust and reviews
  - sterility
  - calculator
  - request form
  - local API
  - SQLite storage
  - Google CRM sync
- Confirmed local route health:
  - `/` -> `200`
  - `/works` -> `200`
  - `/offer` -> `200`
  - `/payment` -> `200`
  - `/privacy` -> `200`
  - `/robokassa/health` -> `200`
- Confirmed website request `#15` with a real form-shaped payload:
  - API response: `201 Created`
  - CRM sync after request: `Lead rows synced: 15`
  - `details_json` keeps the readable pre-order labels:
    - style
    - size
    - placement
    - color
    - complexity
    - price range
    - hours
    - selected work title
- Current review texts on the site already match the two latest testimonials from the user.
- Exact review photos from chat still need local source files if we want to place those same images into `site/images/reviews/`.
