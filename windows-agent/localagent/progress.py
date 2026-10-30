"""Translate observable Codex events into short status messages, never reasoning text."""
import re,time

def command_phase(command):
    if re.search(r'\b(?:pytest|unittest|ctest)\b|\b(?:npm|pnpm|yarn|cargo|go)(?:\.cmd)?\s+(?:run\s+)?test\b',command,re.I):return 'testing'
    if re.search(r'\b(?:npm|pnpm|yarn|cargo|dotnet)(?:\.cmd)?\s+(?:run\s+)?build\b',command,re.I):return 'building'
    return 'executing'

class ProgressEvents:
    def __init__(self,callback,clock=time.monotonic,min_interval=20):
        self.callback=callback;self.clock=clock;self.min_interval=min_interval
        self.last_sent=float('-inf');self.seen=set();self.files=set()
    def emit(self,text,phase,force=False):
        now=self.clock();announce=now-self.last_sent>=(5 if force else self.min_interval)
        if announce:self.last_sent=now
        self.callback(text,phase,announce)
    def event(self,event):
        typ=event.get('type');item=event.get('item') or {}
        if typ=='thread.started':self.emit('Codex подключён, выполняю поручение.','codex')
        elif typ in ('error','turn.failed'):self.emit('Codex сообщил об ошибке. Подробности сохраняются в журнале.','error',True)
        elif typ in ('item.started','item.completed'):
            kind=item.get('type')
            # Do not forward reasoning or arbitrary model text, prompts, stdout, paths or command arguments.
            key=(typ,item.get('id'))
            if item.get('id') and key in self.seen:return
            if item.get('id'):self.seen.add(key)
            if kind=='command_execution':
                phase=command_phase(item.get('command',''))
                if typ=='item.started':
                    label={'testing':'Запускаю команду тестирования.','building':'Запускаю сборку проекта.','executing':'Codex выполняет рабочую команду.'}[phase]
                    self.emit(label,phase)
                else:
                    code=item.get('exit_code')
                    if code is not None and code!=0:
                        self.emit('Одна из команд завершилась с ошибкой. Codex может попробовать другой способ.','command_error',True)
                    elif code==0 and phase=='testing':
                        self.emit('Команда тестирования завершилась без ошибки. Результаты будут в отчёте.','tested',True)
            elif kind=='file_change' and typ=='item.completed':
                for change in item.get('changes',[]):
                    if change.get('path'):self.files.add(change['path'])
                self.emit(f'Codex изменил файлы проекта: {len(self.files)}.','writing')
        elif typ=='turn.completed':self.emit('Codex завершил этап, получаю результат.','codex_done')
