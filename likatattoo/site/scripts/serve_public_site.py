from __future__ import annotations

import argparse
import mimetypes
import socketserver
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = ROOT / "site"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8812

TEXT_TYPES = {
    "application/javascript",
    "application/json",
    "application/manifest+json",
    "image/svg+xml",
}

STATIC_ROUTES = {
    "/": "client.html",
    "/client": "client.html",
    "/client.html": "client.html",
    "/works": "works.html",
    "/works.html": "works.html",
    "/offer": "offer.html",
    "/offer.html": "offer.html",
    "/payment": "payment.html",
    "/payment.html": "payment.html",
    "/privacy": "privacy.html",
    "/privacy.html": "privacy.html",
    "/styles.css": "styles.css",
    "/client-theme.css": "client-theme.css",
    "/client.js": "client.js",
    "/favicon.svg": "favicon.svg",
    "/robots.txt": "robots.txt",
    "/sitemap.xml": "sitemap.xml",
    "/site.webmanifest": "site.webmanifest",
}

ALLOWED_PREFIXES = (
    "/data/",
    "/images/",
)


def resolve_route(raw_path: str) -> Path | None:
    parsed = urlsplit(raw_path)
    path = unquote(parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    file_name = STATIC_ROUTES.get(path)
    if file_name is None:
        for prefix in ALLOWED_PREFIXES:
            if path.startswith(prefix):
                relative = path.lstrip("/")
                file_path = SITE_ROOT / relative
                if file_path.is_file():
                    return file_path
                return None
        return None

    file_path = SITE_ROOT / file_name
    if not file_path.is_file():
        return None
    return file_path


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class PublicSiteHandler(BaseHTTPRequestHandler):
    server_version = "ppdstr-local"
    sys_version = ""

    def do_GET(self) -> None:
        self._serve(send_body=True)

    def do_HEAD(self) -> None:
        self._serve(send_body=False)

    def log_message(self, format: str, *args: object) -> None:
        super().log_message(format, *args)

    def _serve(self, *, send_body: bool) -> None:
        file_path = resolve_route(self.path)
        if file_path is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0]
        if content_type is None and file_path.suffix == ".webmanifest":
            content_type = "application/manifest+json"
        if content_type is None:
            content_type = "application/octet-stream"
        if content_type.startswith("text/") or content_type in TEXT_TYPES:
            content_type = f"{content_type}; charset=utf-8"

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        if send_body:
            self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the public ppdstr site with the same public routes as production."
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with ThreadingTCPServer((args.host, args.port), PublicSiteHandler) as server:
        print(f"Serving public site from {SITE_ROOT} on http://{args.host}:{args.port}/")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
