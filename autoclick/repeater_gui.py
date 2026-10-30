"""Windows-friendly control window for recording and replaying browser actions."""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk


ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "repeater.py"


class RepeaterGUI:
    def __init__(self, root):
        self.root = root
        root.title("Повторитель действий в Chrome")
        root.geometry("820x650")
        self.url = tk.StringVar(value=(ROOT / "demo_site.html").as_uri())
        self.scenario = tk.StringVar(value=str(ROOT / "scenario.json"))
        self.count = tk.StringVar(value="1")
        self.data = tk.StringVar()
        self.proxies = tk.StringVar()
        self.record_proxy = tk.StringVar()
        self.output = tk.StringVar(value=str(ROOT / "replay_output"))
        self.success_text = tk.StringVar()
        self.headless = tk.BooleanVar(value=False)
        self.events = queue.Queue()
        self.process = None
        self.mode = None
        self.closing = False
        self._build()
        root.after(100, self._drain_events)
        root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        form = ttk.Frame(self.root, padding=14)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self._row(form, 0, "Адрес сайта", self.url)
        self._row(form, 1, "Сценарий JSON", self.scenario, save=True)
        self._row(form, 2, "Прокси при записи", self.record_proxy, file=True)
        self._row(form, 3, "Браузеров", self.count)
        self._row(form, 4, "Данные по браузерам", self.data, file=True)
        self._row(form, 5, "Прокси по браузерам", self.proxies, file=True)
        self._row(form, 6, "Папка результата", self.output, directory=True)
        ttk.Checkbutton(form, text="Запуск без окон (не подходит для ручной CAPTCHA)", variable=self.headless).grid(
            row=7, column=1, sticky="w", pady=(4, 8))
        ttk.Label(form, text="Текст успеха").grid(row=8, column=0, sticky="w", pady=3, padx=(0, 8))
        ttk.Entry(form, textvariable=self.success_text).grid(row=8, column=1, sticky="ew", pady=3)
        self.assert_button = ttk.Button(form, text="Добавить проверку", command=self._add_assert)
        self.assert_button.grid(row=8, column=2, padx=(6, 0))

        record_buttons = ttk.Frame(self.root, padding=(14, 0, 14, 4))
        record_buttons.pack(fill="x")
        replay_buttons = ttk.Frame(self.root, padding=(14, 0, 14, 8))
        replay_buttons.pack(fill="x")
        self.record_button = ttk.Button(record_buttons, text="Начать запись", command=self.start_record)
        self.pause_button = ttk.Button(record_buttons, text="Пауза / CAPTCHA", command=lambda: self._send("pause"))
        self.resume_button = ttk.Button(record_buttons, text="Продолжить запись", command=lambda: self._send("resume"))
        self.stop_button = ttk.Button(record_buttons, text="Сохранить запись", command=lambda: self._send("stop"))
        self.replay_button = ttk.Button(replay_buttons, text="Запустить повтор", command=self.start_replay)
        self.continue_button = ttk.Button(replay_buttons, text="Продолжить после CAPTCHA", command=self._continue_manual)
        self.abort_button = ttk.Button(replay_buttons, text="Остановить повтор", command=self._abort)
        for button in (self.record_button, self.pause_button, self.resume_button, self.stop_button):
            button.pack(side="left", padx=3)
        for button in (self.replay_button, self.continue_button, self.abort_button):
            button.pack(side="left", padx=3)

        self.status = tk.StringVar(value="Готово к записи или повтору")
        ttk.Label(self.root, textvariable=self.status, padding=(14, 4)).pack(anchor="w")
        self.log = scrolledtext.ScrolledText(self.root, height=16, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._set_buttons()

    def _row(self, parent, index, label, variable, file=False, save=False, directory=False):
        ttk.Label(parent, text=label).grid(row=index, column=0, sticky="w", pady=3, padx=(0, 8))
        ttk.Entry(parent, textvariable=variable).grid(row=index, column=1, sticky="ew", pady=3)
        if file or save or directory:
            def choose():
                if directory:
                    selected = filedialog.askdirectory()
                elif save:
                    selected = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
                else:
                    selected = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("Все файлы", "*")])
                if selected:
                    variable.set(selected)
            ttk.Button(parent, text="Обзор…", command=choose).grid(row=index, column=2, padx=(6, 0))

    def _log(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", line.rstrip("\n") + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_buttons(self):
        idle = self.mode is None
        recording = self.mode == "record"
        replaying = self.mode == "replay"
        for button, enabled in (
            (self.record_button, idle), (self.replay_button, idle),
            (self.pause_button, recording), (self.resume_button, recording),
            (self.stop_button, recording), (self.assert_button, recording), (self.abort_button, replaying),
            (self.continue_button, replaying and self.status.get().startswith("Ручной шаг")),
        ):
            button.configure(state="normal" if enabled else "disabled")

    def _start(self, mode, command, environment=None):
        if self.mode is not None:
            return
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if environment:
            env.update(environment)
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-u", str(ENGINE), *command],
                cwd=str(ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                bufsize=1, env=env,
            )
        except Exception as error:
            messagebox.showerror("Ошибка запуска", str(error))
            return
        self.mode = mode
        self.status.set("Идёт запись" if mode == "record" else "Идёт повтор")
        self._set_buttons()
        self._log("Запущено: " + " ".join(command))

        def read_output():
            for line in self.process.stdout:
                self.events.put(("line", line))
            self.events.put(("exit", self.process.wait()))

        threading.Thread(target=read_output, daemon=True).start()

    def start_record(self):
        url = self.url.get().strip()
        scenario = self.scenario.get().strip()
        if not url or not scenario:
            messagebox.showerror("Нужны данные", "Укажите адрес сайта и путь сценария")
            return
        command = ["record", url, "--output", scenario]
        if self.record_proxy.get().strip():
            command += ["--proxy", self.record_proxy.get().strip()]
        self._start("record", command)

    def start_replay(self):
        scenario = Path(self.scenario.get().strip())
        if not scenario.is_file():
            messagebox.showerror("Нет сценария", f"Файл не найден: {scenario}")
            return
        try:
            count = int(self.count.get())
            if count < 1:
                raise ValueError
            content = json.loads(scenario.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            messagebox.showerror("Ошибка сценария", str(error))
            return
        secrets = sorted({step["value"]["secret_env"] for step in content.get("steps", [])
                          if isinstance(step, dict) and isinstance(step.get("value"), dict)
                          and "secret_env" in step["value"]})
        environment = {}
        for name in secrets:
            value = simpledialog.askstring("Пароль", f"Введите значение {name}", show="*", parent=self.root)
            if value is None:
                return
            environment[name] = value
        command = ["replay", str(scenario), "--count", str(count), "--output", self.output.get().strip()]
        if self.data.get().strip():
            command += ["--data", self.data.get().strip()]
        if self.proxies.get().strip():
            command += ["--proxies", self.proxies.get().strip()]
        if self.headless.get():
            command.append("--headless")
        self._start("replay", command, environment)

    def _send(self, command):
        if self.process is None or self.process.poll() is not None:
            return
        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            self._log("Команда: " + (command or "продолжить"))
        except (OSError, ValueError) as error:
            self._log(f"Не удалось отправить команду: {error}")

    def _add_assert(self):
        text = self.success_text.get().strip()
        if not text:
            messagebox.showerror("Нет текста", "Введите видимый текст, который означает успешное завершение")
            return
        self._send("assert " + text)

    def _continue_manual(self):
        self._send("")
        self.status.set("Идёт повтор")
        self._set_buttons()

    def _abort(self):
        if self.process is None or self.process.poll() is not None:
            return
        pid = self.process.pid
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, text=True, check=False)
        else:
            self.process.terminate()
        self._log("Повтор остановлен пользователем")

    def _drain_events(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "line":
                line = value.rstrip()
                if line.startswith("REPEATER_WAIT "):
                    self.status.set("Ручной шаг: пройдите проверку в браузере")
                    self._set_buttons()
                self._log(line)
            elif kind == "exit":
                previous_mode = self.mode
                self.mode = None
                self.process = None
                self.status.set("Готово" if value == 0 else f"Ошибка, код {value}")
                self._set_buttons()
                self._log(f"{previous_mode}: завершено с кодом {value}")
                if self.closing:
                    self.root.destroy()
                    return
        self.root.after(100, self._drain_events)

    def _close(self):
        if self.mode == "record":
            self.closing = True
            self._send("stop")
            self.status.set("Сохраняю запись…")
        elif self.mode == "replay":
            self._abort()
            self.root.destroy()
        else:
            self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    RepeaterGUI(window)
    window.mainloop()
