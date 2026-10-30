"""Record browser actions and replay them in independent Chrome instances."""

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright


VIEWPORT = {"width": 1280, "height": 800}
RECORDER_SCRIPT = r"""
(() => {
  if (window.__actionRecorderInstalled) return;
  window.__actionRecorderInstalled = true;

  function unique(selector) {
    try { return document.querySelectorAll(selector).length === 1; }
    catch { return false; }
  }
  function selectorFor(element) {
    if (!(element instanceof Element)) return null;
    for (const attribute of ['data-testid', 'data-test', 'data-qa', 'id', 'name']) {
      const value = element.getAttribute(attribute);
      if (!value) continue;
      const selector = attribute === 'id' ? '#' + CSS.escape(value)
        : `[${attribute}=${JSON.stringify(value)}]`;
      if (unique(selector)) return selector;
    }
    const parts = [];
    let node = element;
    while (node && node !== document.documentElement) {
      if (node.getRootNode() !== document) return null;
      let position = 1;
      for (let sibling = node.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
        if (sibling.tagName === node.tagName) position++;
      }
      parts.unshift(`${node.tagName.toLowerCase()}:nth-of-type(${position})`);
      node = node.parentElement;
    }
    parts.unshift('html');
    return parts.join(' > ');
  }
  function send(action) {
    window.__repeaterEvent(action).catch(() => {});
  }
  function targetOf(event) {
    const path = event.composedPath();
    return path.find(item => item instanceof Element) || event.target;
  }
  document.addEventListener('input', event => {
    const element = targetOf(event);
    if (!element || element.tagName === 'SELECT' || ['checkbox', 'radio', 'file'].includes(element.type)) return;
    const selector = selectorFor(element);
    if (!selector) return;
    const value = element.isContentEditable ? element.innerText : element.value;
    send({type: 'fill', selector, value, secret: element.type === 'password'});
  }, true);
  document.addEventListener('change', event => {
    const element = targetOf(event);
    const selector = selectorFor(element);
    if (!selector) return;
    if (element.type === 'file') send({type: 'upload', selector, value: '{{file_path}}'});
    else if (element.tagName === 'SELECT') send({type: 'select', selector, value: element.value});
    else if (['checkbox', 'radio'].includes(element.type))
      send({type: 'check', selector, checked: element.checked});
  }, true);
  document.addEventListener('click', event => {
    if (event.detail === 0) return; // Keyboard-generated click is represented by keydown.
    const element = targetOf(event);
    if (!element) return;
    if (['INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'LABEL'].includes(element.tagName) || element.isContentEditable) return;
    if (element.tagName === 'CANVAS') {
      send({type: 'click_xy', x: event.clientX, y: event.clientY});
      return;
    }
    const selector = selectorFor(element);
    if (selector) send({type: 'click', selector});
    else send({type: 'click_xy', x: event.clientX, y: event.clientY});
  }, true);
  document.addEventListener('keydown', event => {
    if (!['Enter', 'Escape'].includes(event.key)) return;
    const element = targetOf(event);
    const selector = selectorFor(element);
    if (selector) send({type: 'press', selector, key: event.key});
    else send({type: 'press', key: event.key});
  }, true);
})();
"""


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def secret_name(selector):
    label = re.sub(r"[^A-Z0-9]+", "_", selector.upper()).strip("_")[-40:]
    return "REPEATER_SECRET_" + label


class Recorder:
    def __init__(self, context):
        self.context = context
        self.pages = {}
        self.steps = []
        self.capturing = True
        self.context.on("page", self._register_page)

    async def install(self):
        await self.context.expose_binding("__repeaterEvent", self._on_event)
        await self.context.add_init_script(script=RECORDER_SCRIPT)

    def _register_page(self, page):
        if page in self.pages:
            return
        page_id = len(self.pages)
        self.pages[page] = page_id
        if page_id:
            self.steps.append({"type": "new_page", "page": page_id})
        page.on("framenavigated", lambda frame: self._on_navigation(page, frame))
        if page.url != "about:blank":
            self._on_navigation(page, page.main_frame)

    def _on_navigation(self, page, frame):
        if not self.capturing or frame != page.main_frame or page.url == "about:blank":
            return
        page_id = self.pages[page]
        step = {"type": "goto", "page": page_id, "url": page.url}
        if not self.steps or self.steps[-1] != step:
            self.steps.append(step)

    async def _on_event(self, source, action):
        if not self.capturing:
            return
        page = source["page"]
        if page not in self.pages:
            self._register_page(page)
        if not isinstance(action, dict) or action.get("type") not in {"fill", "select", "check", "click", "click_xy", "press", "upload"}:
            return
        action["page"] = self.pages[page]
        if action.pop("secret", False):
            action["value"] = {"secret_env": secret_name(action["selector"])}
        if action["type"] == "fill" and self.steps and self.steps[-1].get("type") == "fill" and self.steps[-1].get("page") == action["page"] and self.steps[-1].get("selector") == action.get("selector"):
            self.steps[-1] = action
        elif not self.steps or self.steps[-1] != action:
            self.steps.append(action)

    def scenario(self):
        return {"version": 1, "recorded_at": datetime.now(timezone.utc).isoformat(), "viewport": VIEWPORT, "steps": self.steps}


def render(value, row):
    if isinstance(value, dict) and "secret_env" in value:
        name = value["secret_env"]
        if name not in os.environ:
            raise ValueError(f"Не задана переменная окружения {name}")
        return os.environ[name]
    if not isinstance(value, str):
        return value
    def substitute(match):
        key = match.group(1)
        if key not in row:
            raise ValueError(f"Нет значения {key} в данных запуска")
        return str(row[key])
    return re.sub(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}", substitute, value)


async def execute_step(context, pages, pending_pages, step, row, timeout, pause_lock, worker_id):
    kind = step["type"]
    page_id = step.get("page", 0)
    if kind == "new_page":
        pages[page_id] = pending_pages.pop(0) if pending_pages else await context.new_page()
        return
    if kind == "pause":
        async with pause_lock:
            description = step.get("description", "Ручной шаг")
            print(f"REPEATER_WAIT {worker_id}: {description}. Нажмите Enter для продолжения.", flush=True)
            await asyncio.to_thread(input)
        return
    if page_id not in pages:
        raise ValueError(f"Страница {page_id} не открыта")
    page = pages[page_id]
    if kind == "goto":
        url = render(step["url"], row)
        if page.url != url:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    elif kind == "click":
        await page.locator(step["selector"]).click(timeout=timeout)
    elif kind == "click_xy":
        await page.mouse.click(step["x"], step["y"])
    elif kind == "fill":
        await page.locator(step["selector"]).fill(render(step["value"], row), timeout=timeout)
    elif kind == "select":
        await page.locator(step["selector"]).select_option(render(step["value"], row), timeout=timeout)
    elif kind == "upload":
        await page.locator(step["selector"]).set_input_files(render(step["value"], row), timeout=timeout)
    elif kind == "check":
        operation = page.locator(step["selector"]).check if step["checked"] else page.locator(step["selector"]).uncheck
        await operation(timeout=timeout)
    elif kind == "press":
        if "selector" in step:
            await page.locator(step["selector"]).press(step["key"], timeout=timeout)
        else:
            await page.keyboard.press(step["key"])
    elif kind == "assert_text":
        await page.get_by_text(render(step["text"], row)).first.wait_for(state="visible", timeout=timeout)
    elif kind == "assert_url":
        await page.wait_for_url(render(step["url"], row), timeout=timeout)
    else:
        raise ValueError(f"Неизвестное действие: {kind}")


async def replay_one(playwright, scenario, worker_id, row, proxy, args, pause_lock):
    result = {"browser": worker_id, "status": "failed", "completed_steps": 0}
    browser = None
    pages = {}
    pending_pages = []
    try:
        launch_args = {"channel": "chrome", "headless": args.headless}
        if proxy:
            launch_args["proxy"] = proxy
        browser = await playwright.chromium.launch(**launch_args)
        context = await browser.new_context(viewport=scenario.get("viewport", VIEWPORT))
        context.on("page", lambda page: pending_pages.append(page))
        first_page = await context.new_page()
        pages[0] = first_page
        if first_page in pending_pages:
            pending_pages.remove(first_page)
        for index, step in enumerate(scenario["steps"], 1):
            try:
                await execute_step(context, pages, pending_pages, step, row, args.timeout * 1000, pause_lock, worker_id)
            except Exception as error:
                result["failed_step"] = index
                result["error"] = str(error).splitlines()[0]
                active_page = pages.get(step.get("page", 0), first_page)
                screenshot = Path(args.output) / f"browser_{worker_id:02d}_error.png"
                if not active_page.is_closed():
                    try:
                        await active_page.screenshot(path=str(screenshot), timeout=5000)
                    except Exception:
                        pass
                break
            result["completed_steps"] = index
        else:
            result["status"] = "passed"
            open_pages = [page for page in pages.values() if not page.is_closed()]
            if open_pages:
                await open_pages[-1].screenshot(path=str(Path(args.output) / f"browser_{worker_id:02d}_done.png"))
    except Exception as error:
        result["error"] = str(error).splitlines()[0]
    finally:
        if browser is not None:
            await browser.close()
    return result


async def record_command(args):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=False, proxy=read_json(args.proxy) if args.proxy else None)
        context = await browser.new_context(viewport=VIEWPORT)
        recorder = Recorder(context)
        await recorder.install()
        page = await context.new_page()
        await page.goto(args.url, wait_until="domcontentloaded")
        print("Запись идёт. Команды: pause, resume, assert <текст успеха>, stop.")
        try:
            while True:
                raw_command = (await asyncio.to_thread(input, "> ")).strip()
                command = raw_command.lower()
                if command == "stop":
                    break
                if command.startswith("assert ") and raw_command[7:].strip():
                    current_page = max(recorder.pages.items(), key=lambda item: item[1])[1]
                    recorder.steps.append({"type": "assert_text", "page": current_page, "text": raw_command[7:].strip()})
                    print("Проверка результата добавлена.")
                if command == "pause":
                    recorder.steps.append({"type": "pause", "description": "Пройдите проверку в браузере"})
                    recorder.capturing = False
                    print("Запись приостановлена. Пройдите проверку, затем введите resume.")
                if command == "resume":
                    recorder.capturing = True
                    print("Запись продолжена.")
        finally:
            await asyncio.sleep(0.2)
            save_json(args.output, recorder.scenario())
            await browser.close()
    print(f"Сценарий сохранён: {args.output}")


async def replay_command(args):
    scenario = read_json(args.scenario)
    if scenario.get("version") != 1 or not isinstance(scenario.get("steps"), list):
        raise ValueError("Неподдерживаемый формат сценария")
    if args.headless and any(step.get("type") == "pause" for step in scenario["steps"]):
        raise ValueError("Сценарий содержит ручной шаг: запустите без --headless")
    rows = read_json(args.data) if args.data else [{} for _ in range(args.count)]
    proxies = read_json(args.proxies) if args.proxies else [None for _ in range(args.count)]
    if not isinstance(rows, list) or not isinstance(proxies, list) or len(rows) < args.count or len(proxies) < args.count:
        raise ValueError("Данных или прокси меньше, чем браузеров")
    Path(args.output).mkdir(parents=True, exist_ok=True)
    pause_lock = asyncio.Lock()
    async with async_playwright() as playwright:
        tasks = [replay_one(playwright, scenario, i + 1, rows[i], proxies[i], args, pause_lock) for i in range(args.count)]
        results = await asyncio.gather(*tasks)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "results": results}
    save_json(Path(args.output) / "report.json", report)
    print(json.dumps({"passed": sum(r["status"] == "passed" for r in results), "total": args.count}, ensure_ascii=False))
    return 0 if all(r["status"] == "passed" for r in results) else 1


def parse_args():
    parser = argparse.ArgumentParser(description="Запись и повторение действий в Chrome")
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="Записать действия")
    record.add_argument("url")
    record.add_argument("--output", default="scenario.json")
    record.add_argument("--proxy", help="JSON с параметрами одного прокси Playwright")
    replay = commands.add_parser("replay", help="Повторить сценарий")
    replay.add_argument("scenario")
    replay.add_argument("--count", type=int, default=1)
    replay.add_argument("--data", help="JSON-массив данных по браузерам")
    replay.add_argument("--proxies", help="JSON-массив прокси по браузерам")
    replay.add_argument("--output", default="replay_output")
    replay.add_argument("--timeout", type=int, default=20, help="Таймаут действия в секундах")
    replay.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.command == "replay" and (args.count < 1 or args.timeout < 1):
        parser.error("count и timeout должны быть больше нуля")
    return args


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.command == "record":
        asyncio.run(record_command(arguments))
    else:
        raise SystemExit(asyncio.run(replay_command(arguments)))
