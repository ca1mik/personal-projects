# Lika Tattoo

Полноценный проект упаковки тату-мастера: публичная витрина для клиента, внутренний дашборд для менеджмента, документы по запуску, контент-система и рабочие шаблоны.

## Что внутри

### `site/`

- `index.html` - хаб проекта со ссылками на все основные разделы.
- `client.html` - публичная клиентская страница мастера с шаблоном первого сообщения и ChatGPT prompt flow.
- `offer.html` - публичная оферта под запись и бронь.
- `payment.html` - правила оплаты, переноса и возврата.
- `privacy.html` - политика обработки персональных данных.
- `dashboard.html` - внутренний рабочий дашборд с локальным хранением лидов, контента и отзывов.
- `styles.css` - общий стиль для всех страниц.
- `app.js` - логика хаба и калькулятора.
- `dashboard.js` - логика внутреннего дашборда.

### `docs/`

- `launch-pack.md` - стратегия запуска, позиционирование, прайс и финмодель.
- `content-system.md` - съемка, контент-воронка и идеи роликов.
- `operations.md` - операционные чеклисты по площадкам и рутине.
- `templates.md` - сообщения клиентам, описания услуг и тексты профилей.
- `brand-guide.md` - тон общения, визуальный стиль и биос для площадок.
- `content-calendar-30-days.md` - готовый контент-план на 30 дней.
- `client-journey.md` - путь клиента от первого сообщения до зажившего фото и рекомендации.
- `ad-test-plan.md` - безопасный план первого рекламного теста.
- `faq-and-objections.md` - ответы на частые вопросы и возражения.
- `publish-checklist.md` - финальная проверка перед публикацией и запуском рекламы.
- `domain-deploy.md` - как подключить `ppdstr.online` / `ppdstr.ru` к серверу и что проверять по DNS.
- `robokassa-readiness.md` - что уже готово для подключения Robokassa и какие данные еще нужны.

### `tools/`

- `client-pipeline.csv` - трекер заявок и записей.
- `content-planner.csv` - планировщик контента.
- `review-tracker.csv` - учет отзывов и заживших фото.
- `monthly-kpi.csv` - таблица контроля результатов.
- `check_public_domains.ps1` - быстрая проверка DNS/HTTP/HTTPS для `ppdstr.online` и `ppdstr.ru`.
- `README.md` - как пользоваться рабочими файлами.

### `deploy/`

- `nginx/ppdstr.conf` - готовый конфиг для публикации клиентского сайта на `ppdstr.online` с редиректами для алиасов.
- `reg-ru/` - готовый upload-бандл для shared hosting REG.RU и zip для загрузки в `public_html`.

### `assets/`

- `portfolio/lettering` - надписи
- `portfolio/graphics` - графика
- `portfolio/color` - цветные работы
- `portfolio/minimalism` - минимализм
- `portfolio/healed` - зажившие работы
- `reviews` - скрины и видео-отзывы
- `video/raw` - исходники
- `video/edited` - готовые ролики
- `references` - референсы и эскизы
- `brand` - обложки, аватары, логотипы, шрифты и фирменные материалы

## Быстрый старт

1. Открой `open_site.cmd` для хаба проекта.
2. Открой `site/client.html` и замени плейсхолдеры ссылок на реальные контакты.
3. Перенеси лучшие работы в `assets/portfolio/*`.
4. Заполни `tools/client-pipeline.csv` и `tools/content-planner.csv`.
5. Пройди `docs/publish-checklist.md` перед первым запуском.
6. Для оформления группы VK открой `open_vk_kit.cmd` или `site/vk-kit.html`.
7. Перед привязкой домена используй только каталог `site/` как публичный web-root и сверься с `docs/domain-deploy.md`.

## Что уже готово в продукте

- На клиентской странице есть два сценария генерации идей: через Telegram-бота и через свой ChatGPT.
- В боте есть отдельный режим `🧠 Prompt для ChatGPT`, который не тратит баланс генераций и работает как fallback.
- На сайте есть one-click сценарий `Скопировать и открыть ChatGPT`.
- Бот готов к двум сервисным оплатам через Telegram Payments: обычная бронь и портфолио-акция “оплачиваются только расходники”.
- На клиентской странице промо для портфолио уже встроено в прайс и FAQ.
- Подготовлены публичные legal-страницы и отдельный helper-слой Robokassa для `pay-interface`.

## Проверки

### Сайт

- `node --check site/app.js`
- `node --check site/dashboard.js`
- `node --check site/client.js`
- локальный запуск публичного сайта через `python site/scripts/serve_public_site.py --host 127.0.0.1 --port 8812`
- повторяемый smoke-check через `python site/scripts/smoke_check.py`

### Бот

- `python bot/main.py --check`
- `python -m compileall bot/main.py bot/app bot/tests`
- `python -m ruff check bot`
- `python -m mypy bot/main.py bot/app bot/tests`
- `python -m pytest bot/tests`
- `python -m pip_audit -r bot/requirements.txt`

## Что лучше заменить сразу

- имя мастера, если нужен другой вариант написания
- реальные ссылки на VK, Telegram, WhatsApp и карты
- актуальный адрес, если он будет публичным
- фотографии в портфолио и отзывы
- подтвержденные регалии и формулировки про образование

## Примечание

Упоминание медицинского образования, стерильности, стажа и любых профессиональных регалий используйте только в том виде, в котором это можно подтвердить фактами и публично заявлять.

## Временная публикация с этого ПК

- Для сайта есть `run_site_public.cmd` и `stop_site_public.cmd`.
- Для бота есть `run_tattoo_bot.cmd`.
- Для публичных callback-URL Robokassa есть `run_bot_public.cmd` и `stop_bot_public.cmd`.
- `run_bot_public.cmd` открывает временный `localhost.run`-хост для `http://127.0.0.1:8080/robokassa/*`, но сам бот нужно запустить отдельно.
- URL сайта нужно брать из `site-tunnel.out.log`, а URL callback-ов Robokassa - из `bot-tunnel.out.log`.
- `localhost.run` дает временные URL. После обрыва соединения адрес может поменяться, и тогда надо обновить `ROBOKASSA_RESULT_URL`, `ROBOKASSA_SUCCESS_URL`, `ROBOKASSA_FAIL_URL`.

## VK Kit

Для оформления группы VK подготовлены:

- инструкция: `docs/vk-group-kit.md`
- визуальные файлы: `assets/brand/vk`
