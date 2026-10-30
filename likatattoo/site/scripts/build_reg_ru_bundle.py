from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = ROOT / "site"
DEPLOY_ROOT = ROOT / "deploy" / "reg-ru"
SOURCE_DOMAIN = "ppdstr.online"
DEFAULT_DOMAIN = "ppdstr.ru"

PUBLIC_FILES = (
    "client.html",
    "works.html",
    "offer.html",
    "payment.html",
    "privacy.html",
    "styles.css",
    "client-theme.css",
    "client.js",
    "favicon.svg",
    "site.webmanifest",
)

TEXT_FILES = {
    "client.html",
    "works.html",
    "offer.html",
    "payment.html",
    "privacy.html",
    "styles.css",
    "client-theme.css",
    "client.js",
    "site.webmanifest",
}

HTACCESS = """Options -Indexes
DirectoryIndex index.html

RewriteEngine On
RewriteRule ^client/?$ /client.html [L]
RewriteRule ^works/?$ /works.html [L]
RewriteRule ^offer/?$ /offer.html [L]
RewriteRule ^payment/?$ /payment.html [L]
RewriteRule ^privacy/?$ /privacy.html [L]
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a REG.RU shared-hosting upload bundle from the public ppdstr site."
    )
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Primary public domain for canonical URLs.")
    return parser.parse_args()


def transform_text(content: str, domain: str) -> str:
    primary_domain = public_domain(domain)
    return (
        content.replace(f"https://{SOURCE_DOMAIN}", f"https://{primary_domain}")
        .replace("https://ppdstr.ru", f"https://{primary_domain}")
        .replace("https://www.ppdstr.ru", f"https://{primary_domain}")
    )


def public_domain(domain: str) -> str:
    return "www.ppdstr.ru" if domain == "ppdstr.ru" else domain


def write_public_files(destination: Path, domain: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    primary_domain = public_domain(domain)

    for file_name in PUBLIC_FILES:
        source = SITE_ROOT / file_name
        target = destination / file_name

        if file_name in TEXT_FILES:
            content = transform_text(source.read_text(encoding="utf-8"), domain)
            target.write_text(content, encoding="utf-8", newline="\n")
        else:
            shutil.copy2(source, target)

    for directory_name in ("data", "images"):
        source_dir = SITE_ROOT / directory_name
        target_dir = destination / directory_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        if source_dir.exists():
            shutil.copytree(source_dir, target_dir)

    # The shared-hosting root should open the public client page, not the internal project hub.
    client_html = transform_text((SITE_ROOT / "client.html").read_text(encoding="utf-8"), domain)
    (destination / "index.html").write_text(client_html, encoding="utf-8", newline="\n")

    robots = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /index.html",
            "Disallow: /dashboard.html",
            "Disallow: /vk-kit.html",
            "Disallow: /scripts/",
            "Disallow: /*-preview.png",
            "",
            f"Sitemap: https://{primary_domain}/sitemap.xml",
            "",
        ]
    )
    (destination / "robots.txt").write_text(robots, encoding="utf-8", newline="\n")

    sitemap = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            "  <url>",
            f"    <loc>https://{primary_domain}/</loc>",
            "    <lastmod>2026-06-05</lastmod>",
            "  </url>",
            "  <url>",
            f"    <loc>https://{primary_domain}/offer</loc>",
            "    <lastmod>2026-06-05</lastmod>",
            "  </url>",
            "  <url>",
            f"    <loc>https://{primary_domain}/works</loc>",
            "    <lastmod>2026-06-05</lastmod>",
            "  </url>",
            "  <url>",
            f"    <loc>https://{primary_domain}/payment</loc>",
            "    <lastmod>2026-06-05</lastmod>",
            "  </url>",
            "  <url>",
            f"    <loc>https://{primary_domain}/privacy</loc>",
            "    <lastmod>2026-06-05</lastmod>",
            "  </url>",
            "</urlset>",
            "",
        ]
    )
    (destination / "sitemap.xml").write_text(sitemap, encoding="utf-8", newline="\n")

    (destination / ".htaccess").write_text(HTACCESS, encoding="utf-8", newline="\n")


def build_zip(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()

    # Create a zip archive of the entire public_html directory, preserving the folder hierarchy.
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, arcname=file_path.relative_to(source_dir))


def main() -> int:
    args = parse_args()
    domain = args.domain.strip().lower()
    bundle_root = DEPLOY_ROOT / domain
    public_html = bundle_root / "public_html"
    zip_path = DEPLOY_ROOT / f"{domain}-upload.zip"

    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)

    write_public_files(public_html, domain)
    build_zip(public_html, zip_path)

    print(f"Built REG.RU bundle for {domain}")
    print(f"Folder: {public_html}")
    print(f"Zip:    {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
