import os
import httpx
from fastapi import FastAPI,Request
from fastapi.responses import Response,RedirectResponse

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
BACKEND='http://127.0.0.1:'+os.environ['FASAD_BACKEND_PORT']
FRONTEND='http://127.0.0.1:'+os.environ['FASAD_FRONTEND_PORT']
DROP={'host','connection','transfer-encoding','content-length','content-encoding','keep-alive'}

@app.api_route('/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'])
async def forward(path:str,request:Request):
    if not path:return RedirectResponse('/connect')
    target=BACKEND if path.startswith(('connect','api/v1','health')) else FRONTEND
    headers={k:v for k,v in request.headers.items() if k.lower() not in DROP}
    headers['host']=request.headers['host']
    if target==BACKEND and path.startswith('api/v1') and 'authorization' not in headers:
        token=request.cookies.get('access_token')
        if token:headers['authorization']='Bearer '+token
    if int(request.headers.get('content-length','0'))>30*1024*1024:return Response('File is too large',status_code=413)
    try:
        async with httpx.AsyncClient(timeout=120,follow_redirects=False,trust_env=False) as client:
            response=await client.request(request.method,target+'/'+path,params=request.query_params,headers=headers,content=await request.body())
        result=Response(content=response.content,status_code=response.status_code)
        result.raw_headers=[(k,v) for k,v in response.headers.raw if k.decode().lower() not in DROP]
        return result
    except httpx.HTTPError:
        return Response('Приложение запускается. Обновите страницу через несколько секунд.',status_code=503,media_type='text/plain; charset=utf-8')
