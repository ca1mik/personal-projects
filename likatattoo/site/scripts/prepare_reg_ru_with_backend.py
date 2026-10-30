from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
SITE_HTML = ROOT / "site" / "client.html"
BOT_ENV = ROOT / "bot" / ".env"
BOT_TUNNEL_LOG = ROOT / "bot-tunnel.out.log"
BUILD_SCRIPT = ROOT / "site" / "scripts" / "build_reg_ru_bundle.py"

REQUEST_API_ATTR = re.compile(r'data-request-api-url="[^"]*"')
PUBLIC_HOST_RE = re.compile(r"https://([a-z0-9]+\.lhr\.life)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject the latest public backend URL into the public site and rebuild the REG.RU upload bundle."
    )
    parser.add_argument(
        "--host",
        default="",
        help="Optional public backend host like abcd1234.lhr.life. If omitted, the script reads bot-tunnel.out.log.",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip external health verification of the public backend URL.",
    )
    return parser.parse_args()


def read_public_host(log_path: Path) -> str:
    if not log_path.exists():
        raise FileNotFoundError(f"Tunnel log not found: {log_path}")
    raw = log_path.read_text(encoding="utf-8", errors="ignore")
    matches = PUBLIC_HOST_RE.findall(raw)
    if not matches:
        raise RuntimeError(f"Could not find a public localhost.run host in {log_path}")
    return matches[-1]


def verify_health(public_host: str) -> None:
    url = f"https://{public_host}/robokassa/health"
    try:
        with urlopen(url, timeout=20) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except URLError as error:
        raise RuntimeError(f"Public backend health check failed for {url}: {error}") from error
    if '"ok": true' not in payload and '"ok":true' not in payload:
        raise RuntimeError(f"Unexpected health response from {url}: {payload}")


def patch_request_api(site_html: Path, endpoint: str) -> None:
    content = site_html.read_text(encoding="utf-8")
    patched = REQUEST_API_ATTR.sub(f'data-request-api-url="{endpoint}"', content, count=1)
    if patched == content:
        raise RuntimeError("Could not update data-request-api-url in site/client.html")
    site_html.write_text(patched, encoding="utf-8", newline="\n")


def upsert_env(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    prefix = f"{key}="
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{value}"
            break
    else:
        lines.append(f"{prefix}{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def patch_robokassa_env(env_path: Path, public_host: str) -> None:
    base = f"https://{public_host}/robokassa"
    upsert_env(env_path, "ROBOKASSA_RESULT_URL", f"{base}/result")
    upsert_env(env_path, "ROBOKASSA_SUCCESS_URL", f"{base}/success")
    upsert_env(env_path, "ROBOKASSA_FAIL_URL", f"{base}/fail")
    upsert_env(env_path, "ROBOKASSA_SUCCESS_URL_METHOD", "GET")
    upsert_env(env_path, "ROBOKASSA_FAIL_URL_METHOD", "GET")


def rebuild_bundle() -> None:
    subprocess.run([sys.executable, str(BUILD_SCRIPT)], cwd=ROOT, check=True)


def main() -> int:
    args = parse_args()
    public_host = args.host.strip() or read_public_host(BOT_TUNNEL_LOG)
    endpoint = f"https://{public_host}/api/booking-request"

    if not args.skip_health_check:
        verify_health(public_host)

    patch_request_api(SITE_HTML, endpoint)
    patch_robokassa_env(BOT_ENV, public_host)
    rebuild_bundle()

    print("Prepared REG.RU deploy bundle with public backend")
    print(f"Public backend host: {public_host}")
    print(f"Website request API: {endpoint}")
    print(f"Robokassa Result URL: https://{public_host}/robokassa/result")
    print(f"Bundle: {ROOT / 'deploy' / 'reg-ru' / 'ppdstr.ru-upload.zip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
