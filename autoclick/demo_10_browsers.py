"""Run the same form chain in ten independent Chrome instances.

Usage: python demo_10_browsers.py
Requires: pip install playwright pillow; an installed Google Chrome.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "demo_output"
COUNT = 10


async def run_one(playwright, number: int, ready: asyncio.Event, release: asyncio.Event):
    browser = None
    page = None
    username = f"demo_user_{number:02d}"
    record = {"browser": number, "username": username, "status": "failed", "steps": []}
    try:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        context = await browser.new_context(viewport={"width": 760, "height": 680})
        page = await context.new_page()
        await page.goto((ROOT / "demo_site.html").as_uri())
        await page.locator("#username").fill(username)
        await page.locator("#password").fill("demo_password")
        await page.get_by_role("button", name="Войти").click()
        await page.get_by_text("Шаг 2/4: данные").wait_for()
        record["steps"].append("login")

        await page.locator("#full_name").fill(f"Тестовый пользователь {number:02d}")
        await page.locator("#email").fill(f"user{number:02d}@example.test")
        await page.get_by_role("button", name="Продолжить").click()
        await page.get_by_text("Шаг 3/4: заявка").wait_for()
        record["steps"].append("profile")

        await page.locator("#service").select_option("demo")
        await page.locator("#comment").fill(f"Заявка номер {number:02d}")
        await page.get_by_role("button", name="Проверить").click()
        await page.get_by_text("Шаг 4/4: проверка").wait_for()
        record["steps"].append("order")

        await page.get_by_role("button", name="Подтвердить").click()
        await page.get_by_text("Заявка успешно создана").wait_for()
        await page.get_by_text(f"Пользователь: {username}; заявка: Заявка номер {number:02d}").wait_for()
        record["steps"].append("finish")
        record["status"] = "passed"
        await page.screenshot(path=str(OUTPUT / f"browser_{number:02d}.png"))
        ready.set()
        await release.wait()  # All ten browser processes are alive at this barrier.
    except Exception as error:
        record["error"] = str(error)
        if page is not None:
            await page.screenshot(path=str(OUTPUT / f"browser_{number:02d}_error.png"))
    finally:
        ready.set()
        if browser is not None:
            await browser.close()
    return record


def make_contact_sheet():
    images = [Image.open(OUTPUT / f"browser_{n:02d}.png").convert("RGB") for n in range(1, COUNT + 1)]
    thumb_width, thumb_height = 380, 170
    sheet = Image.new("RGB", (thumb_width * 5, (thumb_height + 28) * 2), "#ffffff")
    draw = ImageDraw.Draw(sheet)
    for index, original in enumerate(images):
        x, y = (index % 5) * thumb_width, (index // 5) * (thumb_height + 28)
        draw.text((x + 8, y + 6), f"Chrome instance {index + 1:02d}", fill="#101828")
        sheet.paste(original.crop((0, 0, 760, 340)).resize((thumb_width, thumb_height)), (x, y + 28))
    sheet.save(OUTPUT / "all_10_browsers.png")


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as playwright:
        ready_events = [asyncio.Event() for _ in range(COUNT)]
        release = asyncio.Event()
        tasks = [asyncio.create_task(run_one(playwright, n, ready_events[n - 1], release)) for n in range(1, COUNT + 1)]
        await asyncio.gather(*(event.wait() for event in ready_events))
        release.set()
        results = await asyncio.gather(*tasks)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "browser_count": COUNT, "results": results}
    (OUTPUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if all(result["status"] == "passed" for result in results):
        make_contact_sheet()
    print(json.dumps({"passed": sum(r["status"] == "passed" for r in results), "total": COUNT}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
