from pathlib import Path
from urllib.parse import urlparse
import asyncio, json, os, secrets, sqlite3, subprocess, sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from store import Store, now

ROOT = Path(__file__).resolve().parent
MODES = {'healthy': 'Всё работает', 'silent_drop': 'Тихая потеря заявки', 'server_error': 'Ошибка сервера'}


def create_app(db_path=None, base=None):
    store = Store(db_path or ROOT / 'data/guardian.sqlite3')
    base = (base or os.environ.get('GUARDIAN_BASE_URL', 'http://127.0.0.1:8782')).rstrip('/')
    target = urlparse(base)
    if target.scheme != 'http' or target.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('Only this local demonstration can be checked')
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    csrf = secrets.token_urlsafe(32)
    app = FastAPI(title='Дозор заявок · локальный прототип', docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.state.store = store
    app.state.jobs = set()
    async def object_body(request):
        raw = await request.body()
        if len(raw) > 4096:
            raise HTTPException(413, 'Слишком большой запрос для тестовой формы')
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, 'Ожидается JSON-объект')
        if not isinstance(data, dict):
            raise HTTPException(422, 'Ожидается JSON-объект')
        return data
    # A restart never turns an unfinished check into a success.
    with store.db() as c:
        c.execute("UPDATE runs SET status='error',finished=?,result=? WHERE status='running'",
                  (now(), json.dumps({'status': 'error', 'code': 'interrupted', 'steps': [],
                                     'message': 'Сервер перезапущен до окончания проверки.'}, ensure_ascii=False)))

    @app.middleware('http')
    async def protect(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail': 'Запрос с другого сайта запрещён'}, status_code=403)
            if not secrets.compare_digest(request.headers.get('x-guardian-token', ''), csrf):
                return JSONResponse({'detail': 'Обновите страницу перед действием'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/')
    def home():
        return FileResponse(ROOT / 'static/index.html')

    @app.get('/demo')
    def demo():
        return FileResponse(ROOT / 'static/demo.html')

    @app.get('/api/state')
    def state():
        with store.db() as c:
            leads = [dict(r) for r in c.execute('SELECT * FROM leads ORDER BY id DESC LIMIT 12')]
        return {'mode': store.mode(), 'modes': MODES, 'token': csrf,
                'runs': store.runs(), 'leads': leads, 'target': base + '/demo'}

    @app.post('/api/mode')
    async def mode(request: Request):
        data = await object_body(request)
        if not isinstance(data.get('mode'), str) or data['mode'] not in MODES:
            raise HTTPException(422, 'Неизвестный режим')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM runs WHERE status='running'").fetchone():
                raise HTTPException(409, 'Дождитесь окончания текущей проверки')
            c.execute("UPDATE settings SET value=? WHERE key='mode'", (data['mode'],))
        return {'saved': True}

    @app.post('/api/demo/submit')
    async def submit(request: Request):
        data = await object_body(request)
        for field in ('name', 'email', 'marker'):
            if not isinstance(data.get(field), str) or not 1 <= len(data[field]) <= 160:
                raise HTTPException(422, 'Проверьте поля тестовой заявки')
        if data['email'] != 'monitor@example.invalid' or not data['marker'].startswith('guardian-'):
            raise HTTPException(422, 'Демо принимает только обозначенные тестовые данные')
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            selected = c.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
            if selected == 'server_error':
                raise HTTPException(503, 'Учебная ошибка сервера')
            if selected == 'healthy':
                c.execute('INSERT OR IGNORE INTO leads(marker,name,email,at) VALUES(?,?,?,?)',
                          (data['marker'], data['name'], data['email'], now()))
        # silent_drop deliberately reproduces a misleading success screen.
        return {'accepted': True, 'message': 'Спасибо! Форма приняла тестовую заявку.'}

    @app.get('/api/demo/receipt/{marker}')
    def receipt(marker: str):
        return {'receipt': store.receipt(marker)}

    async def start_worker(ident, marker):
        def execute():
            process = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'check.py'),
                                      '--base', base, '--marker', marker,
                                      '--screenshot', str(artifacts / f'run-{ident}.png')],
                                     cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=35,
                                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            if process.returncode != 0:
                raise RuntimeError('Процесс проверки завершился с ошибкой')
            return json.loads(process.stdout)
        try:
            result = await asyncio.to_thread(execute)
            if result.get('status') not in ('passed', 'failed', 'error'):
                raise ValueError('Некорректный результат проверки')
        except Exception as exc:
            result = {'status': 'error', 'code': 'worker_error', 'steps': [],
                      'message': 'Проверка не завершена: ' + str(exc)[:300]}
        store.finish(ident, result)

    app.state.worker = start_worker

    @app.post('/api/run')
    async def run():
        marker = 'guardian-' + secrets.token_hex(12)
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM runs WHERE status='running'").fetchone():
                raise HTTPException(409, 'Проверка уже выполняется')
            selected = c.execute("SELECT value FROM settings WHERE key='mode'").fetchone()[0]
            ident = c.execute('INSERT INTO runs(marker,mode,status,started) VALUES(?,?,?,?)',
                              (marker, selected, 'running', now())).lastrowid
        task = asyncio.create_task(app.state.worker(ident, marker))
        app.state.jobs.add(task)
        task.add_done_callback(app.state.jobs.discard)
        return {'id': ident, 'marker': marker}

    app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    app.mount('/artifacts', StaticFiles(directory=artifacts), name='artifacts')
    return app


app = create_app()
