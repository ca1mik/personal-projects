import pytest
from fastapi.testclient import TestClient
from app import create_app
from store import Store, now


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'guardian.sqlite3')
    c = TestClient(app)
    c.headers['x-guardian-token'] = c.get('/api/state').json()['token']
    return c, app


def lead(marker):
    return {'name': 'Тест', 'email': 'monitor@example.invalid', 'marker': marker}


def test_receipt_matches_exact_run_and_survives_restart(client):
    c, app = client
    assert c.post('/api/demo/submit', json=lead('guardian-first')).status_code == 200
    assert c.post('/api/demo/submit', json=lead('guardian-second')).status_code == 200
    assert c.get('/api/demo/receipt/guardian-first').json()['receipt']['marker'] == 'guardian-first'
    assert c.get('/api/demo/receipt/guardian-missing').json()['receipt'] is None
    # Repeated delivery is idempotent, not a second lead.
    assert c.post('/api/demo/submit', json=lead('guardian-first')).status_code == 200
    assert len(c.get('/api/state').json()['leads']) == 2
    reopened = Store(app.state.store.path)
    assert reopened.receipt('guardian-first')


def test_silent_loss_returns_success_but_no_delivery(client):
    c, _ = client
    c.post('/api/demo/submit', json=lead('guardian-old'))
    assert c.post('/api/mode', json={'mode': 'silent_drop'}).status_code == 200
    r = c.post('/api/demo/submit', json=lead('guardian-lost'))
    assert r.status_code == 200 and r.json()['accepted'] is True
    assert c.get('/api/demo/receipt/guardian-lost').json()['receipt'] is None
    assert c.get('/api/demo/receipt/guardian-old').json()['receipt']


def test_server_failure_and_non_test_data_are_not_accepted(client):
    c, _ = client
    assert c.post('/api/demo/submit', json={**lead('guardian-real'), 'email': 'real@example.com'}).status_code == 422
    assert c.post('/api/mode', json={'mode': ['healthy']}).status_code == 422
    assert c.post('/api/mode', content='broken json').status_code == 422
    c.post('/api/mode', json={'mode': 'server_error'})
    assert c.post('/api/demo/submit', json=lead('guardian-error')).status_code == 503
    assert c.get('/api/demo/receipt/guardian-error').json()['receipt'] is None


def test_origin_token_and_target_restrictions(client):
    c, _ = client
    assert c.post('/api/mode', json={'mode': 'healthy'}, headers={'Origin': 'https://other.example'}).status_code == 403
    assert c.post('/api/run', headers={'x-guardian-token': 'wrong'}).status_code == 403
    assert c.get('/', headers={'Host': 'attacker.example'}).status_code == 400
    with pytest.raises(ValueError):
        create_app(base='http://third-party.example')


def test_active_run_blocks_mode_changes_and_restart_reports_interruption(client):
    c, app = client
    with app.state.store.db() as db:
        ident = db.execute('INSERT INTO runs(marker,mode,status,started) VALUES(?,?,?,?)',
                           ('guardian-active', 'healthy', 'running', now())).lastrowid
    assert c.post('/api/mode', json={'mode': 'silent_drop'}).status_code == 409
    assert c.post('/api/run').status_code == 409
    restarted = create_app(app.state.store.path)
    run = restarted.state.store.runs()[0]
    assert run['id'] == ident and run['status'] == 'error'
    assert run['result']['code'] == 'interrupted'


def test_completed_result_persists(client):
    _, app = client
    with app.state.store.db() as db:
        ident = db.execute('INSERT INTO runs(marker,mode,status,started) VALUES(?,?,?,?)',
                           ('guardian-completed', 'silent_drop', 'running', now())).lastrowid
    result = {'status': 'failed', 'code': 'delivery_missing', 'steps': [{'name': 'CRM', 'ok': False}]}
    app.state.store.finish(ident, result)
    restarted = create_app(app.state.store.path)
    assert restarted.state.store.runs()[0]['result'] == result
