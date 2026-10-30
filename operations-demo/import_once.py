"""Optional CLI for the same initial import used by the setup screen."""
import argparse,base64
from pathlib import Path
from fastapi.testclient import TestClient
from app import create_app

def main():
    p=argparse.ArgumentParser();p.add_argument('--db');
    for area in ('production','welding','docs'):p.add_argument('--'+area,required=True)
    a=p.parse_args()
    files={area:base64.b64encode(Path(getattr(a,area)).read_bytes()).decode() for area in ('production','welding','docs')}
    with TestClient(create_app(a.db)) as c:
        login=c.post('/api/login',json={'username':'admin','password':'demo-admin-2026'});login.raise_for_status()
        c.headers['x-csrf-token']=login.json()['csrf']
        r=c.post('/api/import',json={'files':files})
        print(r.json());r.raise_for_status()
if __name__=='__main__':main()
