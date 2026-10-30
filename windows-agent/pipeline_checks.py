"""Queue acceptance checks. Ingress is explicitly local, not forged Telegram user messages."""
import time
import win32com.client
from localagent.base import ROOT,Store

voice=win32com.client.Dispatch('SAPI.SpVoice')
for token in voice.GetVoices():
    if 'Irina' in token.GetDescription():voice.Voice=token;break
path=ROOT.parents[1]/'work'/'voice-pipeline.wav'
stream=win32com.client.Dispatch('SAPI.SpFileStream');stream.Open(str(path),3,False);voice.AudioOutputStream=stream
voice.Speak('Скажи одним предложением, что голосовые сообщения работают.');stream.Close()
s=Store();chat=s.kv('owner_chat')
print('Voice pipeline task:',s.enqueue(chat,'[VOICE_FILE] '+str(path),'integration-voice'))
s.execute('INSERT OR IGNORE INTO schedules VALUES(?,?,?,?,?,1)',('installation-once',chat,
    'Внутренняя проверка планировщика. Ответь одним коротким предложением: напоминания по расписанию работают. Никаких действий на компьютере.',0,time.time()+3))
print('One-time scheduler check created.')
