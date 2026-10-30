from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import Any

from .utils import write_json, write_text


SUMMARY_FIELDS = [
    "source_video",
    "clip_id",
    "clip_type",
    "start",
    "end",
    "duration",
    "text",
    "hook",
    "cta",
    "caption",
    "viral_score",
    "conversion_score",
    "retention_score",
    "tattoo_visual_score",
    "motion_score",
    "brightness_score",
    "total_score",
    "reason",
    "best",
    "output_file",
    "files",
]


def write_video_report(report_path: Path, payload: dict[str, Any]) -> Path:
    """Write per-video JSON report."""
    write_json(report_path, payload)
    return report_path


def write_summary_reports(rows: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    """Write summary CSV and HTML reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "summary.csv"
    html_path = output_dir / "summary.html"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in SUMMARY_FIELDS})

    header = "".join(f"<th>{html.escape(field)}</th>" for field in SUMMARY_FIELDS)
    table_rows: list[str] = []
    for row in rows:
        cells = "".join(
            f"<td>{html.escape(str(row.get(field, '')))}</td>"
            for field in SUMMARY_FIELDS
        )
        table_rows.append(f"<tr>{cells}</tr>")

    html_body = (
        "<html><head><meta charset='utf-8'><title>video-auto-cutter report</title>"
        "<style>body{font-family:Arial,sans-serif;padding:24px}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ddd;padding:8px;vertical-align:top}th{background:#f2f2f2}"
        "td{font-size:13px;line-height:1.35}</style></head><body>"
        "<h1>video-auto-cutter summary</h1>"
        f"<p>Всего клипов: {len(rows)}</p>"
        f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(table_rows)}</tbody></table>"
        "</body></html>"
    )
    write_text(html_path, html_body)
    return csv_path, html_path
