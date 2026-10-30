# Open Claw Agent (Windows)

## Install
1) Python 3.11+ (желательно)
2) В папке проекта:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

3) Создай .env:
   copy .env.example .env
   заполни TG_BOT_TOKEN и ALLOWED_USER_IDS

4) Запуск:
   python -m src.main

## Telegram
- Создай бота через @BotFather, возьми token
- Узнай свой user_id через @userinfobot

## Autostart (варианты)
### A) Task Scheduler (просто)
- Create Task -> At log on
- Action: Program/script: python
- Add arguments: -m src.main
- Start in: путь к папке open-claw-agent

### B) NSSM (как сервис)
- nssm install OpenClawAgent
- Path: python.exe
- Arguments: -m src.main
- Startup directory: путь к проекту
