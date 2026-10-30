# 🧑‍💻 Web3 Bio — Калдин Лев

Персональный портфолио-сайт и Telegram-бот визитка для **Калдина Льва** — Python / AI Automation Engineer.

## 🚀 Стек

- **Frontend**: React 19 + Vite 8 (SPA)
- **Styling**: Vanilla CSS (dark theme, glassmorphism, animations)
- **Bot**: Node.js + `node-telegram-bot-api`
- **Scripts**: Node.js утилиты для Telegram и сканирования проектов

## 📂 Структура

```
src/
  App.jsx       — основной React-компонент (Hero, Nav, Секции)
  App.css       — все стили (design tokens, компоненты)
  bio.js        — данные профиля (имя, опыт, проекты, контакты)
  main.jsx      — точка входа React

scripts/
  bot.js            — Telegram-бот визитка с inline-меню
  fetchTelegram.js  — забирает последние посты из канала → public/data/telegram.json
  scanProjects.js   — сканирует папку с проектами → public/data/projects.json

public/
  favicon.svg
  data/             — генерируемые JSON-данные
```

## 🛠 Команды

```bash
# Запустить dev-сервер
npm run dev

# Собрать продакшн
npm run build

# Запустить Telegram-бот
npm run bot

# Получить посты из Telegram-канала
npm run fetch:tg

# Сгенерировать список проектов
npm run fetch:projects
```

## ⚙️ Настройка (.env)

```env
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHANNEL_ID=@ваш_канал
```

## 📝 Персонализация

Все данные профиля — в файле [`src/bio.js`](src/bio.js):
- `name`, `fullName`, `tagline` — имя и специализация
- `description` — текст «Обо мне»
- `skills` — список навыков
- `workExperience` — опыт работы (timeline)
- `projects` — портфолио проектов
- `contacts` — телефон, email, Telegram
- `wallet` — EVM-адрес кошелька (опционально)

Бот-данные — в [`scripts/bot.js`](scripts/bot.js) в блоке `BIO`.
