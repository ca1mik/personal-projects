import asyncio
from localagent.telegram import Telegram

async def main():
    tg=Telegram()
    commands=[('help','Что умеет помощник'),('ping','Проверить связь'),('sync','Связь с этим чатом Codex'),('selftest','Проверить команды бота'),('ask','Поручение в этот чат Codex'),('status','Состояние компьютера'),('tasks','Мои задачи'),('progress','Что сейчас делает Codex'),('history','История задач'),
              ('news','Свежие новости'),('joke','Добрая шутка'),('meme','Смешной мем'),('cute','Милая картинка'),('idea','Идея стартапа'),('mail','Важные письма'),('plan','План дня'),('feed','Личная подборка и её настройки'),('topics','Мои интересы'),('remind','Напомнить: 20м текст'),('reminders','Мои напоминания'),('save','Сохранить заметку'),('saved','Сохранённые идеи'),
              ('screenshot','Снимок экрана'),('hh','Поиск вакансий'),('hhstats','Статистика откликов'),('schedules','Расписания'),
              ('stop','Аварийная пауза'),('resume','Продолжить работу')]
    commands=[('home','Панель помощника'),('memory','Что я помню о тебе'),('remember','Запомнить факт'),('forget','Забыть факт по ID'),('mode','Режим помощника')]+commands
    commands += [('power','Управление компьютером'),('shutdown','Выключить ПК через 60 секунд'),('reboot','Перезагрузить ПК через 60 секунд'),('cancelshutdown','Отменить выключение или перезагрузку'),('power_test','Проверка выключения с немедленной отменой')]
    try:
        result=await tg.call('setMyCommands',commands=[{'command':k,'description':v} for k,v in commands])
        print('Telegram command menu configured:',result)
    finally:await tg.client.aclose()

if __name__=='__main__':asyncio.run(main())
