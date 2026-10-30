"""Verified portable SQLite + file-storage snapshots.

Run from backend: python -m scripts.backup once|loop|status|verify PATH|restore PATH TARGET
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings

BACKUP_DIR = Path(__file__).resolve().parents[1] / "backups"


def _remove_snapshot(path: Path, backup_dir: Path) -> None:
    if path.is_symlink() or path.resolve().parent != backup_dir.resolve():
        raise RuntimeError("Refusing to delete backup outside configured directory")
    shutil.rmtree(path)


def _sqlite_path() -> Path:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("sqlite") or url.database in (None, "", ":memory:"):
        raise RuntimeError("Portable backup supports file-based SQLite only; use pg_dump for PostgreSQL")
    return Path(url.database).resolve()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(snapshot: Path) -> None:
    snapshot = snapshot.resolve()
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    for name, expected in files.items():
        path = (snapshot / name).resolve()
        if snapshot not in path.parents or not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Invalid backup file: {name}")
        if _hash(path) != expected:
            raise RuntimeError(f"Backup checksum mismatch: {name}")
    actual = {str(path.relative_to(snapshot)).replace("\\", "/") for path in snapshot.rglob("*") if path.is_file() and path.name != "manifest.json"}
    if actual != set(files):
        raise RuntimeError("Backup file list differs from manifest")
    connection = sqlite3.connect(f"file:{(snapshot / 'database.sqlite').as_posix()}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup database integrity check failed")
    finally:
        connection.close()


def create_snapshot(backup_dir: Path = BACKUP_DIR, *, keep: int = 14) -> Path:
    source_db = _sqlite_path()
    storage = get_settings().local_storage_path.resolve()
    backup_dir = backup_dir.resolve()
    if not source_db.is_file():
        raise RuntimeError(f"Database does not exist: {source_db}")
    if backup_dir == storage or storage in backup_dir.parents or backup_dir in storage.parents:
        raise RuntimeError("Backup directory and file storage must be separate")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    temporary = backup_dir / f".{stamp}.partial"
    final = backup_dir / stamp
    temporary.mkdir()
    try:
        source = sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True)
        destination = sqlite3.connect(temporary / "database.sqlite")
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        files = {"database.sqlite": _hash(temporary / "database.sqlite")}
        if storage.exists():
            for entry in storage.rglob("*"):
                if entry.is_symlink():
                    raise RuntimeError("Storage contains a symlink; backup aborted")
                if not entry.is_file():
                    continue
                relative = entry.relative_to(storage)
                target = temporary / "storage" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(entry, target)
                files[str(target.relative_to(temporary)).replace("\\", "/")] = _hash(target)
        (temporary / "manifest.json").write_text(
            json.dumps({"created_at": datetime.now(UTC).isoformat(), "files": files}, indent=2),
            encoding="utf-8",
        )
        verify(temporary)
        temporary.rename(final)
    except Exception:
        _remove_snapshot(temporary, backup_dir)
        raise
    snapshots = sorted((path for path in backup_dir.iterdir() if path.is_dir() and not path.name.startswith(".")), reverse=True)
    for old in snapshots[max(keep, 1):]:
        _remove_snapshot(old, backup_dir)
    mirror = get_settings().backup_mirror_path
    if mirror is not None:
        mirror = mirror.resolve()
        if mirror == backup_dir or mirror in backup_dir.parents or backup_dir in mirror.parents or mirror == storage or mirror in storage.parents or storage in mirror.parents:
            raise RuntimeError("Backup mirror must be separate from local backups and file storage")
        mirror.mkdir(parents=True, exist_ok=True)
        mirror_temporary = mirror / f".{stamp}.partial"
        mirror_final = mirror / stamp
        shutil.copytree(final, mirror_temporary)
        try:
            verify(mirror_temporary)
            mirror_temporary.rename(mirror_final)
        except Exception:
            _remove_snapshot(mirror_temporary, mirror)
            raise
        mirrored = sorted((path for path in mirror.iterdir() if path.is_dir() and not path.name.startswith(".")), reverse=True)
        for old in mirrored[max(keep, 1):]:
            _remove_snapshot(old, mirror)
    return final


def restore(snapshot: Path, target: Path) -> Path:
    """Stage a verified restore in a new directory; never overwrite live data."""
    verify(snapshot)
    target = target.resolve()
    if target.exists():
        raise RuntimeError(f"Restore target already exists: {target}")
    target.mkdir(parents=True)
    try:
        shutil.copy2(snapshot / "database.sqlite", target / "app.db")
        if (snapshot / "storage").exists():
            shutil.copytree(snapshot / "storage", target / "storage_data")
    except Exception:
        shutil.rmtree(target)
        raise
    return target


def status(backup_dir: Path = BACKUP_DIR, *, max_age_hours: int = 26) -> dict[str, str]:
    """Fail loudly if the latest local or configured mirror copy is stale or invalid."""
    if not backup_dir.is_dir():
        raise RuntimeError("Backup directory does not exist")
    snapshots = sorted((path for path in backup_dir.iterdir()
                        if path.is_dir() and not path.name.startswith(".")), reverse=True)
    if not snapshots:
        raise RuntimeError("No backup snapshots found")
    latest = snapshots[0]
    verify(latest)
    manifest = json.loads((latest / "manifest.json").read_text(encoding="utf-8"))
    created = datetime.fromisoformat(manifest["created_at"])
    age_hours = (datetime.now(UTC) - created).total_seconds() / 3600
    if age_hours > max_age_hours:
        raise RuntimeError(f"Latest backup is too old: {age_hours:.1f} hours")
    mirror = get_settings().backup_mirror_path
    if mirror is not None:
        mirrored = mirror / latest.name
        if not mirrored.is_dir():
            raise RuntimeError("Latest backup is missing from configured mirror")
        verify(mirrored)
    return {"latest": str(latest), "created_at": created.isoformat(),
            "mirror": str(mirror / latest.name) if mirror else "not configured"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("once", "loop", "status", "verify", "restore"))
    parser.add_argument("snapshot", nargs="?", type=Path)
    parser.add_argument("target", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "verify":
        if args.snapshot is None:
            parser.error("verify requires a snapshot path")
        verify(args.snapshot)
        print("Backup verified:", args.snapshot)
    elif args.action == "restore":
        if args.snapshot is None or args.target is None:
            parser.error("restore requires a snapshot and a new target directory")
        print("Restore staged:", restore(args.snapshot, args.target))
    elif args.action == "once":
        print("Backup created:", create_snapshot())
    elif args.action == "status":
        print(json.dumps(status(), ensure_ascii=False))
    else:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                message = f"{datetime.now(UTC).isoformat()} Backup created: {create_snapshot()}"
            except Exception as exc:
                message = f"{datetime.now(UTC).isoformat()} Backup failed: {exc}"
            with (BACKUP_DIR / "backup.log").open("a", encoding="utf-8") as log:
                log.write(message + "\n")
            print(message, flush=True)
            time.sleep(24 * 60 * 60)


if __name__ == "__main__":
    main()
