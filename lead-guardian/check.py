"""One isolated browser check. The dashboard launches this worker on demand.

No existing browser profile, real email or third-party CRM is used.
"""
from pathlib import Path
from urllib.parse import urlparse
import argparse, json, os, sys, time
from playwright.sync_api import sync_playwright


def check(base, marker, screenshot):
    parsed = urlparse(base)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('This prototype only checks its own loopback demonstration')
    steps = []
    result = {'status': 'error', 'code': 'browser_error', 'steps': steps,
              'message': 'Проверка не завершилась', 'screenshot': None}
    page = None
    started = time.monotonic()
    with sync_playwright() as p:
        channel = os.environ.get('GUARDIAN_BROWSER_CHANNEL')
        if channel is None and sys.platform == 'win32':
            channel = 'msedge'
        browser = p.chromium.launch(headless=True, **({'channel': channel} if channel else {}))
        try:
            page = browser.new_page(viewport={'width': 1080, 'height': 800})
            # Deny external requests: this demonstration cannot send leads to other sites.
            page.route('**/*', lambda route: route.continue_()
                       if route.request.url.startswith(base + '/') else route.abort())
            page.set_default_timeout(7000)
            response = page.goto(base + '/demo', wait_until='domcontentloaded')
            if not response or response.status != 200:
                raise RuntimeError('Тестовая страница недоступна')
            steps.append({'name': 'Страница открылась', 'ok': True})
            page.get_by_label('Имя').fill('Тест Дозора')
            page.get_by_label('Email').fill('monitor@example.invalid')
            page.get_by_label('Метка проверки').fill(marker)
            with page.expect_response(lambda r: r.url == base + '/api/demo/submit') as submitted:
                page.get_by_role('button', name='Отправить тестовую заявку').click()
            response = submitted.value
            if response.status != 200:
                steps.append({'name': 'Сервер принял заявку', 'ok': False})
                page.get_by_role('status').filter(has_text='Ошибка').wait_for()
                result.update(status='failed', code='submit_error',
                              message='Отправка формы завершилась ошибкой сервера. Заявка не доставлена.')
            else:
                page.get_by_role('status').filter(has_text='Спасибо').wait_for()
                steps.append({'name': 'Форма показала подтверждение', 'ok': True})
                # A UI confirmation alone is insufficient. Match this run's exact marker.
                receipt = None
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    r = page.request.get(base + '/api/demo/receipt/' + marker)
                    if r.status != 200:
                        raise RuntimeError('CRM недоступна для подтверждения доставки')
                    receipt = r.json()['receipt']
                    if receipt:
                        break
                    time.sleep(0.25)
                steps.append({'name': 'Та же заявка найдена в тестовой CRM' if receipt
                              else 'Заявка не найдена в тестовой CRM', 'ok': bool(receipt)})
                if receipt:
                    result.update(status='passed', code='delivered', receipt=receipt,
                                  message='Заявка прошла форму и найдена в тестовой CRM по уникальной метке.')
                else:
                    result.update(status='failed', code='delivery_missing',
                                  message='Сайт показал «Спасибо», но эта заявка не появилась в тестовой CRM за 3 секунды.')
        except Exception as exc:
            result.update(status='error', code='check_error',
                          message='Проверяющий не смог завершить сценарий. Доставка этой заявки не подтверждена.',
                          diagnostic=str(exc)[:800])
        finally:
            if page:
                try:
                    page.screenshot(path=str(screenshot), full_page=True)
                    result['screenshot'] = Path(screenshot).name
                except Exception:
                    pass
            browser.close()
    result['elapsed_ms'] = round((time.monotonic() - started) * 1000)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--marker', required=True)
    parser.add_argument('--screenshot', required=True)
    args = parser.parse_args()
    try:
        result = check(args.base, args.marker, args.screenshot)
    except Exception as exc:
        result = {'status': 'error', 'code': 'worker_error', 'steps': [],
                  'message': 'Браузер проверки не запустился. Проверьте установку Edge или Chromium.',
                  'diagnostic': str(exc)[:800], 'screenshot': None}
    print(json.dumps(result, ensure_ascii=False))
