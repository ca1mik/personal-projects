"""Smoke test the GUI controls and the subprocess bridge without manual clicks."""

import json
import tempfile
import time
import tkinter as tk
from pathlib import Path

from repeater_gui import RepeaterGUI


ROOT = Path(__file__).resolve().parent


def pump_until(root, predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError("GUI did not reach the expected state")


def main():
    root = tk.Tk()
    root.withdraw()
    app = RepeaterGUI(root)
    try:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            scenario = folder / "scenario.json"
            app.url.set((ROOT / "demo_site.html").as_uri())
            app.scenario.set(str(scenario))
            app.output.set(str(folder / "output"))
            app.start_record()
            pump_until(root, lambda: app.process is not None and app.process.poll() is None)
            time.sleep(0.4)
            app.success_text.set("Тестовый сайт")
            app._add_assert()
            app._send("stop")
            pump_until(root, lambda: app.mode is None)
            assert scenario.is_file()
            recorded = json.loads(scenario.read_text(encoding="utf-8"))
            assert any(step["type"] == "goto" for step in recorded["steps"])
            assert any(step["type"] == "assert_text" for step in recorded["steps"])

            app.headless.set(True)
            app.count.set("10")
            app.start_replay()
            pump_until(root, lambda: app.mode is None)
            report = json.loads((folder / "output" / "report.json").read_text(encoding="utf-8"))
            assert len(report["results"]) == 10 and all(result["status"] == "passed" for result in report["results"]), report

            recorded["steps"].append({"type": "pause", "description": "Тестовая проверка"})
            scenario.write_text(json.dumps(recorded, ensure_ascii=False), encoding="utf-8")
            app.headless.set(False)
            app.count.set("1")
            app.start_replay()
            pump_until(root, lambda: app.status.get().startswith("Ручной шаг"))
            assert str(app.continue_button["state"]) == "normal"
            app._continue_manual()
            pump_until(root, lambda: app.mode is None)
            report = json.loads((folder / "output" / "report.json").read_text(encoding="utf-8"))
            assert report["results"][0]["status"] == "passed", report
            print("GUI record, replay, and manual pause passed")
    finally:
        if app.mode == "record":
            app._send("stop")
        elif app.mode == "replay":
            app._abort()
        root.destroy()


if __name__ == "__main__":
    main()
