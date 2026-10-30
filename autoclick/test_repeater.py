"""End-to-end check: record a form chain, then replay in ten Chrome instances."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from playwright.async_api import async_playwright

from repeater import Recorder, replay_command, save_json


ROOT = Path(__file__).resolve().parent


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context()
        recorder = Recorder(context)
        await recorder.install()
        page = await context.new_page()
        await page.goto((ROOT / "demo_site.html").as_uri())
        await page.locator("#username").fill("recorded_user")
        await page.locator("#password").fill("private_demo_password")
        await page.get_by_role("button", name="Войти").click()
        await page.locator("#full_name").fill("Recorded Name")
        await page.locator("#email").fill("recorded@example.test")
        await page.get_by_role("button", name="Продолжить").click()
        await page.locator("#comment").fill("Recorded request")
        await page.get_by_role("button", name="Проверить").click()
        await page.get_by_role("button", name="Подтвердить").click()
        await page.get_by_text("Заявка успешно создана").wait_for()
        await asyncio.sleep(0.3)
        scenario = recorder.scenario()
        await browser.close()

    serialized = json.dumps(scenario, ensure_ascii=False)
    assert "private_demo_password" not in serialized, "Password leaked into scenario"
    assert any(step["type"] == "click" for step in scenario["steps"])
    assert any(step["type"] == "fill" for step in scenario["steps"])
    for step in scenario["steps"]:
        if step["type"] == "fill":
            step["value"] = {
                "#username": "{{username}}",
                "#full_name": "{{full_name}}",
                "#email": "{{email}}",
                "#comment": "{{comment}}",
            }.get(step["selector"], step["value"])
    scenario["steps"].append({"type": "assert_text", "page": 0, "text": "Заявка успешно создана"})

    os.environ["REPEATER_SECRET_PASSWORD"] = "demo_password"
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        scenario_path = folder / "scenario.json"
        rows_path = folder / "rows.json"
        save_json(scenario_path, scenario)
        save_json(rows_path, [
            {"username": f"demo_user_{i:02d}", "full_name": f"User {i}",
             "email": f"user{i}@example.test", "comment": f"Request {i}"}
            for i in range(1, 11)
        ])
        args = SimpleNamespace(scenario=str(scenario_path), count=10, data=str(rows_path),
                               proxies=None, output=str(folder / "output"), timeout=20, headless=True)
        code = await replay_command(args)
        report = json.loads((folder / "output" / "report.json").read_text(encoding="utf-8"))
        assert code == 0, report
        assert len(list((folder / "output").glob("browser_*_done.png"))) == 10
        print(f"Recorded {len(scenario['steps'])} steps; replay passed in 10/10 browsers")

        broken = json.loads(json.dumps(scenario, ensure_ascii=False))
        broken["steps"][-1]["text"] = "Несуществующее подтверждение"
        bad_path = folder / "broken.json"
        save_json(bad_path, broken)
        bad_args = SimpleNamespace(scenario=str(bad_path), count=1, data=str(rows_path),
                                   proxies=None, output=str(folder / "bad_output"), timeout=1, headless=True)
        assert await replay_command(bad_args) == 1
        bad_report = json.loads((folder / "bad_output" / "report.json").read_text(encoding="utf-8"))
        assert bad_report["results"][0]["status"] == "failed"
        assert bad_report["results"][0]["failed_step"] == len(broken["steps"])
        assert (folder / "bad_output" / "browser_01_error.png").is_file()
        print("Missing final confirmation correctly reported as failure")

    # A real link navigation must stay after the click in the recorded sequence.
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        first = folder / "first.html"
        second = folder / "second.html"
        first.write_text('<a id="next" href="second.html">Next</a>', encoding="utf-8")
        second.write_text('<h1>Arrived</h1>', encoding="utf-8")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
            context = await browser.new_context()
            recorder = Recorder(context)
            await recorder.install()
            page = await context.new_page()
            await page.goto(first.as_uri())
            await page.locator("#next").click()
            await page.get_by_text("Arrived").wait_for()
            await asyncio.sleep(0.2)
            navigation_scenario = recorder.scenario()
            await browser.close()
        types = [step["type"] for step in navigation_scenario["steps"]]
        assert types == ["goto", "click", "goto"], navigation_scenario
        navigation_scenario["steps"].append({"type": "assert_text", "page": 0, "text": "Arrived"})
        nav_path = folder / "navigation.json"
        save_json(nav_path, navigation_scenario)
        args = SimpleNamespace(scenario=str(nav_path), count=1, data=None, proxies=None,
                               output=str(folder / "output"), timeout=20, headless=True)
        assert await replay_command(args) == 0
        print("Link navigation recorded and replayed")

    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        first = folder / "first.html"
        second = folder / "second.html"
        first.write_text('<a id="popup" href="second.html" target="_blank">Open</a>', encoding="utf-8")
        second.write_text('<h1>Popup arrived</h1>', encoding="utf-8")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
            context = await browser.new_context()
            recorder = Recorder(context)
            await recorder.install()
            page = await context.new_page()
            await page.goto(first.as_uri())
            async with context.expect_page() as popup_info:
                await page.locator("#popup").click()
            popup = await popup_info.value
            await popup.get_by_text("Popup arrived").wait_for()
            await asyncio.sleep(0.2)
            popup_scenario = recorder.scenario()
            await browser.close()
        types = [step["type"] for step in popup_scenario["steps"]]
        assert types == ["goto", "click", "new_page", "goto"], popup_scenario
        popup_scenario["steps"].append({"type": "assert_text", "page": 1, "text": "Popup arrived"})
        popup_path = folder / "popup.json"
        save_json(popup_path, popup_scenario)
        args = SimpleNamespace(scenario=str(popup_path), count=1, data=None, proxies=None,
                               output=str(folder / "output"), timeout=20, headless=True)
        assert await replay_command(args) == 0
        print("New tab recorded and replayed")


if __name__ == "__main__":
    asyncio.run(main())
