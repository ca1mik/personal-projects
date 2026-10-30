"""Local demo accounts, password hashes and server-side session checks."""
import hashlib,hmac,secrets,sqlite3,time
from datetime import datetime,timezone
from fastapi import HTTPException

ROLES={'admin':'Администратор','director':'Директор','production':'Заготовка','welding':'Сварка','docs':'Документация'}

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),240000).hex()

def password_ok(password,stored):
    try:return hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored)
    except (ValueError,AttributeError):return False

def initialize(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT NOT NULL UNIQUE,name TEXT NOT NULL,role TEXT NOT NULL,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user INTEGER NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS login_attempts(key TEXT,at REAL);
    ''')
    if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        for role,name in ROLES.items():
            c.execute('INSERT INTO users(username,name,role,password_hash) VALUES(?,?,?,?)',(role,name,role,password_hash('demo-'+role+'-2026')))

def public(user):return {k:user[k] for k in ('id','username','name','role','active')}

def session(c,token):
    r=c.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user WHERE s.token=? AND s.expires>? AND u.active=1',(token,time.time())).fetchone()
    return dict(r) if r else None

def can_edit(user,area):return user['role']=='admin' or user['role']==area
def can_read(user,area):return user['role'] in ('admin','director',area)

def require_edit(request,area):
    if not can_edit(request.state.user,area):raise HTTPException(403,'Нет доступа к изменению этого участка')

def require_admin(request):
    if request.state.user['role']!='admin':raise HTTPException(403,'Только администратор может управлять доступом')

def register(app,db,audit):
    from fastapi import Request
    from fastapi.responses import JSONResponse
    @app.middleware('http')
    async def authorize(request,call_next):
        if not request.url.path.startswith('/api/'):return await call_next(request)
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Запрос с другого сайта запрещён'},status_code=403)
        if request.url.path=='/api/login':return await call_next(request)
        with db() as c:user=session(c,request.cookies.get('kontur_session',''))
        if not user:return JSONResponse({'detail':'Войдите в систему'},status_code=401)
        if request.method not in ('GET','HEAD','OPTIONS') and not hmac.compare_digest(request.headers.get('x-csrf-token',''),user['csrf']):
            return JSONResponse({'detail':'Сессия устарела. Обновите страницу'},status_code=403)
        request.state.user=user
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        return response
    @app.post('/api/login')
    async def login(request:Request):
        try:data=await request.json()
        except ValueError:raise HTTPException(422,'Проверьте логин и пароль')
        if not isinstance(data,dict):raise HTTPException(422,'Ожидается объект')
        username=data.get('username','');password=data.get('password','')
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>80 or len(password)>200:raise HTTPException(422,'Проверьте логин и пароль')
        key=(request.client.host if request.client else 'local')+':'+username
        with db() as c:
            c.execute('DELETE FROM login_attempts WHERE at<?',(time.time()-900,))
            if c.execute('SELECT COUNT(*) FROM login_attempts WHERE key=?',(key,)).fetchone()[0]>=10:raise HTTPException(429,'Слишком много попыток. Повторите через 15 минут')
            u=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
            if not u or not u['active'] or not password_ok(password,u['password_hash']):
                c.execute('INSERT INTO login_attempts VALUES(?,?)',(key,time.time()))
                # Commit the failure counter before raising outside the transaction.
                failed=True
            else:
                failed=False;c.execute('DELETE FROM login_attempts WHERE key=?',(key,))
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                c.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
                c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token,u['id'],csrf,time.time()+8*3600))
                audit(c,'login',None,None,{'username':username},username)
        if failed:raise HTTPException(401,'Неверный логин или пароль')
        response=JSONResponse({'user':public(u),'csrf':csrf})
        response.set_cookie('kontur_session',token,httponly=True,samesite='strict',max_age=8*3600)
        response.headers['Cache-Control']='no-store'
        return response
    @app.get('/api/me')
    def me(request:Request):return {'user':public(request.state.user),'csrf':request.state.user['csrf'],'roles':ROLES}
    @app.post('/api/logout')
    def logout(request:Request):
        with db() as c:
            c.execute('DELETE FROM sessions WHERE token=?',(request.cookies.get('kontur_session',''),))
            audit(c,'logout',None,None,None,request.state.user['username'])
        response=JSONResponse({'logged_out':True});response.delete_cookie('kontur_session');return response
    @app.get('/api/users')
    def users(request:Request):
        require_admin(request)
        with db() as c:return {'users':[public(r) for r in c.execute('SELECT * FROM users ORDER BY id')],'roles':ROLES}
    @app.get('/api/roles')
    def roles(request:Request):
        require_admin(request)
        areas=('production','welding','docs')
        return {'roles':[{'id':r,'name':n,'read_areas':[a for a in areas if can_read({'role':r},a)],
                         'edit_areas':[a for a in areas if can_edit({'role':r},a)],
                         'manage_users':r=='admin','import':r=='admin','export':True,
                         'restore':r!='director','assign_tasks':r in ('admin','director'),
                         'progress_tasks':r!='director'} for r,n in ROLES.items()]}
    async def user_data(request):
        try:d=await request.json()
        except ValueError:raise HTTPException(422,'Некорректные данные')
        if not isinstance(d,dict):raise HTTPException(422,'Ожидается объект')
        if d.get('role') not in ROLES:raise HTTPException(422,'Выберите существующую роль')
        if not isinstance(d.get('name'),str) or not d['name'].strip() or len(d['name'])>100:raise HTTPException(422,'Укажите имя до 100 символов')
        pw=d.get('password','')
        if not isinstance(pw,str) or (pw and not 10<=len(pw)<=200):raise HTTPException(422,'Пароль должен содержать от 10 до 200 символов')
        if type(d.get('active',True)) is not bool:raise HTTPException(422,'Неверное состояние доступа')
        return d
    @app.post('/api/users')
    async def create_user(request:Request):
        require_admin(request);d=await user_data(request)
        username=d.get('username','')
        import re
        if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}',username):raise HTTPException(422,'Логин: 3–40 латинских букв, цифр, точек или дефисов')
        if not d.get('password'):raise HTTPException(422,'Задайте пароль')
        try:
            with db() as c:
                ident=c.execute('INSERT INTO users(username,name,role,password_hash,active) VALUES(?,?,?,?,?)',(username,d['name'].strip(),d['role'],password_hash(d['password']),d.get('active',True))).lastrowid
                audit(c,'user_create',None,None,{'username':username,'name':d['name'],'role':d['role'],'active':d.get('active',True)},request.state.user['username'])
        except sqlite3.IntegrityError:raise HTTPException(409,'Логин уже существует')
        return {'id':ident}
    @app.put('/api/users/{ident}')
    async def update_user(ident:int,request:Request):
        require_admin(request);d=await user_data(request)
        with db() as c:
            c.execute('BEGIN IMMEDIATE');u=c.execute('SELECT * FROM users WHERE id=?',(ident,)).fetchone()
            if not u:raise HTTPException(404,'Пользователь не найден')
            active=d.get('active',True)
            if ident==request.state.user['id'] and (not active or d['role']!='admin'):raise HTTPException(409,'Нельзя отключить или понизить собственный доступ администратора')
            if u['role']=='admin' and u['active'] and (not active or d['role']!='admin') and c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1:raise HTTPException(409,'В системе должен оставаться активный администратор')
            c.execute('UPDATE users SET name=?,role=?,active=?,password_hash=? WHERE id=?',(d['name'].strip(),d['role'],active,password_hash(d['password']) if d.get('password') else u['password_hash'],ident))
            if not active or d.get('password'):c.execute('DELETE FROM sessions WHERE user=?',(ident,))
            after={'username':u['username'],'name':d['name'],'role':d['role'],'active':active}
            if d.get('password'):after['password_changed']=True
            audit(c,'user_update',None,public(u),after,request.state.user['username'])
        return {'saved':True}
