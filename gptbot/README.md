# Telegram Desktop Assistant

Telegram-бот для удаленного управления Windows-ПК.

Что умеет:

- чат с LLM через `codex.sale`
- локальная модель через `Ollama`
- голосовые сообщения из Telegram с расшифровкой
- поиск файлов по имени и по содержимому
- список окон, фокус, сворачивание и восстановление
- запуск приложений, файлов и ссылок
- горячие клавиши и ввод текста в активное окно
- клик мышью по координатам
- скриншоты экрана
- создание писем и встреч в Outlook
- fallback в текстовый черновик и `.ics`, если Outlook отвечает слишком долго

## Запуск

```bash
npm install
npm start
```

## Основные команды

- `/help`
- `/status`
- `/provider codexsale`
- `/provider ollama`
- `/model list`
- `/model имя_модели`
- `/find договор`
- `/grep номер счета`
- `/windows`
- `/focus chrome`
- `/minimize`
- `/restore telegram`
- `/open notepad`
- `/keys ctrl+s`
- `/type привет`
- `/click 300 500`
- `/screenshot`
- `/mail user@example.com|Тема|Текст письма`
- `/sendmail user@example.com|Тема|Текст письма`
- `/event Встреча|2026-06-27 14:00|60|Офис|Обсудить демо`
- `/reset`

## Примеры без команд

- `сделай скрин`
- `найди файл договор`
- `найди в файлах номер клиента`
- `открой notepad`
- `нажми ctrl+s`
- `введи Добрый день`
