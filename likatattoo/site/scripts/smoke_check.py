from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORT = 8819
SERVER_SCRIPT = ROOT / "site" / "scripts" / "serve_public_site.py"

PAGES = (
    ("/", 'data-page="home"'),
    ("/client.html", 'data-page="home"'),
    ("/works", 'data-page="works"'),
    ("/offer", 'class="legal-page"'),
    ("/payment", 'class="legal-page"'),
    ("/privacy", 'class="legal-page"'),
    ("/client-theme.css", ".ppd-hero"),
    ("/data/consumables.json", '"minimum_charge"'),
    ("/data/portfolio.json", '"items"'),
    ("/data/booking-snapshot.json", '"slots"'),
    ("/robots.txt", "Sitemap: https://www.ppdstr.ru/sitemap.xml"),
    ("/sitemap.xml", "<loc>https://www.ppdstr.ru/works</loc>"),
    ("/site.webmanifest", '"name": "ppdstr"'),
    ("/favicon.svg", "<svg"),
)

BINARY_ASSETS = (
    "/images/process/session-long-01.mov",
    "/images/process/prep-process-01.mov",
    "/images/master/master-portrait-01.webp",
)

BLOCKED_PATHS = (
    "/index.html",
    "/dashboard.html",
    "/vk-kit.html",
    "/app.js",
    "/dashboard.js",
)


def fetch(path: str) -> tuple[int, str]:
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def wait_until_ready(process: subprocess.Popen[str]) -> None:
    for _ in range(40):
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise RuntimeError(f"Server exited early with code {process.returncode}.\n{output}")
        try:
            status, _ = fetch("/")
            if status == 200:
                return
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Timed out while waiting for local public site server.")


def fetch_binary(path: str) -> tuple[int, bytes]:
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> int:
    process = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT), "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_until_ready(process)

        for path, expected_text in PAGES:
            status, body = fetch(path)
            if status != 200:
                raise RuntimeError(f"{path}: expected 200, got {status}")
            if expected_text not in body:
                raise RuntimeError(f"{path}: expected marker {expected_text!r} not found")
            print(f"OK {path}")

        for path in BINARY_ASSETS:
            status, body = fetch_binary(path)
            if status != 200:
                raise RuntimeError(f"{path}: expected 200, got {status}")
            if not body:
                raise RuntimeError(f"{path}: expected non-empty binary payload")
            print(f"OK {path}")

        for path in BLOCKED_PATHS:
            status, _ = fetch(path)
            if status != 404:
                raise RuntimeError(f"{path}: expected 404, got {status}")
            print(f"OK {path} -> 404")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
