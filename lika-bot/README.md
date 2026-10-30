# Lika Birthday Bot

Романтичный Telegram-бот-подарок на день рождения для Лики. Это не сервисный бот, а интерактивный сценарий на весь день: с постепенным раскрытием, тёплыми сообщениями, локальными видео, скрытыми разделами, финалом и аккуратной админкой.

## Что умеет бот

- отправляет красивое стартовое поздравление и мягкий вводный сценарий;
- показывает живое инлайн-меню вместо сухих системных фраз;
- работает с локальными видео по категориям и не повторяет уже отправленные ролики;
- хранит прогресс в SQLite отдельно по `user_id`;
- считает, сколько сюрпризов уже открыто и сколько ещё ждёт;
- открывает скрытые разделы по условиям;
- шлёт сценарные сообщения по расписанию через APScheduler;
- замечает новые видео в папках и может уведомить Лику;
- поддерживает админ-команды `/sync`, `/stats`, `/broadcast_test`, `/send_final_now`, `/debug_progress`, `/reschedule`.

## Стек

- Python 3.12+
- aiogram 3
- SQLite + `aiosqlite`
- APScheduler
- python-dotenv

## Структура проекта

```text
f:\likahb
├─ main.py
├─ .env.example
├─ requirements.txt
├─ README.md
├─ assets/
│  └─ videos/
│     ├─ README.md
│     ├─ random/
│     ├─ family/
│     ├─ friends/
│     ├─ sister/
│     ├─ from_me/
│     ├─ special/
│     └─ final/
├─ data/
└─ lika_bot/
   ├─ app.py
   ├─ config/
   │  └─ settings.py
   ├─ db/
   │  ├─ database.py
   │  └─ schema.py
   ├─ handlers/
   │  ├─ admin.py
   │  └─ user.py
   ├─ keyboards/
   │  └─ inline.py
   ├─ models/
   │  └─ entities.py
   ├─ repositories/
   │  ├─ progress.py
   │  ├─ scheduled.py
   │  ├─ users.py
   │  └─ videos.py
   ├─ scheduler/
   │  └─ manager.py
   ├─ services/
   │  ├─ access.py
   │  ├─ content_sync.py
   │  ├─ progress.py
   │  ├─ story.py
   │  └─ video.py
   ├─ texts/
   │  └─ content.py
   └─ utils/
      ├─ files.py
      ├─ logging.py
      └─ time.py
```

## Быстрый запуск

1. Создай виртуальное окружение:

```bash
python -m venv .venv
```

2. Активируй его:

```bash
.venv\Scripts\activate
```

3. Установи зависимости:

```bash
pip install -r requirements.txt
```

4. Создай `.env` на основе примера:

```bash
copy .env.example .env
```

5. Заполни обязательные переменные:

- `BOT_TOKEN` - токен Telegram-бота;
- `ADMIN_ID` - твой Telegram user id;
- `LIKA_CHAT_ID` - user id Лики;
- `BIRTHDAY_DATE` - дата дня рождения в формате `YYYY-MM-DD`.

6. Запусти бота:

```bash
python main.py
```

## Переменные окружения

Минимально важные:

- `BOT_TOKEN=`
- `ADMIN_ID=`
- `LIKA_CHAT_ID=`
- `TIMEZONE=Europe/Amsterdam`
- `BIRTHDAY_DATE=2026-04-23`
- `DB_PATH=data/lika_bot.sqlite3`
- `ASSETS_DIR=assets`
- `AUTO_SCAN_ENABLED=true`
- `AUTO_SCAN_INTERVAL_MINUTES=30`
- `ENABLE_SCHEDULED_MESSAGES=true`

Дополнительные для тонкой настройки:

- `TOTAL_SURPRISES=19`
- `SPECIAL_UNLOCK_VIDEO_COUNT=3`
- `FINAL_UNLOCK_VIDEO_COUNT=7`
- `FINAL_UNLOCK_TOTAL_OPENED=13`
- `FINAL_UNLOCK_TIME=22:00`
- `ALLOW_GUESTS=false`
- `LOG_LEVEL=INFO`

## Как загрузить видео

Бот читает видео из `assets/videos/` и автоматически определяет категорию по названию папки.

Примеры:

- `assets/videos/family/pozdravlenie_ot_mamy.mp4`
- `assets/videos/friends/party_clip.mov`
- `assets/videos/from_me/for_lika_01.mp4`
- `assets/videos/special/secret.mp4`
- `assets/videos/final/finale.mp4`

Важно:

- одинаковый файл не будет отправляться повторно одной и той же пользовательнице, пока в выбранной области не закончатся все доступные видео;
- если папка пуста, бот не падает и отвечает красиво;
- новые файлы можно добавлять прямо во время работы бота.

## Как работает синхронизация новых видео

Есть два пути:

1. Ручной:

```text
/sync
```

2. Автоматический:

- включается через `AUTO_SCAN_ENABLED=true`;
- интервал задаётся через `AUTO_SCAN_INTERVAL_MINUTES`.

Во время синхронизации бот:

- сканирует папки;
- добавляет новые файлы в таблицу `videos`;
- выключает отсутствующие файлы через `is_active = 0`;
- при появлении новых сюрпризов отправляет Лике уведомление.

## Как работают скрытые кнопки

Логика вынесена в настройки:

- `Особенный сюрприз` открывается после `SPECIAL_UNLOCK_VIDEO_COUNT` просмотренных видео;
- `Финал дня` открывается либо после `FINAL_UNLOCK_VIDEO_COUNT` видео, либо после достижения `FINAL_UNLOCK_TOTAL_OPENED`, либо после времени `FINAL_UNLOCK_TIME`;
- логика реализована в [lika_bot/services/progress.py](/f:/likahb/lika_bot/services/progress.py).

Если хочется сделать сценарий мягче или быстрее:

- поменяй значения в `.env`;
- перезапусти бота;
- при необходимости выполни `/reschedule`.

## Как работает расписание

Сценарные сообщения лежат в [lika_bot/texts/content.py](/f:/likahb/lika_bot/texts/content.py) в списке `STORY_MOMENTS`.

Там можно менять:

- время;
- текст;
- количество сообщений в течение дня;
- финальную ночную точку на следующий день.

Планировщик:

- создаётся в [lika_bot/scheduler/manager.py](/f:/likahb/lika_bot/scheduler/manager.py);
- не дублирует уже отправленные сообщения;
- умеет заново пересоздавать задания через `/reschedule`;
- имеет мягкий fallback для недавних пропущенных задач при рестарте.

## Как поменять тексты

Все основные тексты собраны в [lika_bot/texts/content.py](/f:/likahb/lika_bot/texts/content.py):

- главное поздравление;
- почасовые сообщения;
- личные послания;
- тексты пустых разделов;
- тексты скрытых кнопок;
- финал дня.

После редактирования текста просто перезапусти бота.

## Админ-команды

- `/sync` - пересканировать видео и обнаружить новые файлы;
- `/stats` - краткая статистика по боту;
- `/broadcast_test` - тестовая отправка сообщения Лике;
- `/send_final_now` - принудительно отправить финал;
- `/debug_progress` - отладочная информация по прогрессу;
- `/reschedule` - пересоздать задачи APScheduler.

Все эти команды доступны только `ADMIN_ID`.

## База данных

SQLite-схема находится в [lika_bot/db/schema.py](/f:/likahb/lika_bot/db/schema.py).

Основные таблицы:

- `users`
- `videos`
- `sent_videos`
- `messages_progress`
- `scheduled_notifications`
- `personal_messages_progress`

## Деплой на VPS

Минимальный сценарий:

1. Установи Python 3.12+ и `ffmpeg` при необходимости для проверки медиа.
2. Склонируй проект на сервер.
3. Создай `.venv` и установи зависимости.
4. Настрой `.env`.
5. Положи видео в `assets/videos/...`.
6. Запусти бота через `systemd`, `supervisor` или `pm2` в режиме plain process.

Пример `systemd`-сервиса:

```ini
[Unit]
Description=Lika Birthday Bot
After=network.target

[Service]
WorkingDirectory=/opt/lika-birthday-bot
ExecStart=/opt/lika-birthday-bot/.venv/bin/python /opt/lika-birthday-bot/main.py
Restart=always
RestartSec=5
User=botuser

[Install]
WantedBy=multi-user.target
```

## Что ещё можно поменять под себя

- перенести видео по более точным категориям;
- увеличить или уменьшить `TOTAL_SURPRISES`;
- заменить тексты на более личные;
- вложить отдельный финальный ролик в `assets/videos/final/`;
- открыть гостевой режим через `ALLOW_GUESTS=true`, если потом захочется расширить бот на несколько пользователей.

## Проверка

Базовая синтаксическая проверка уже проходится командой:

```bash
python -m compileall main.py lika_bot
```

Для полного запуска нужны установленные зависимости и валидный `.env`.
