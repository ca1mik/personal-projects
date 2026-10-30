import os
from pathlib import Path

try:
    import psutil
except Exception:
    psutil = None


EXCLUDED_DIRS = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "ProgramData",
    ".git",
    "__pycache__",
    "node_modules",
}

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".xlsx", ".xls", ".pptx", ".md"}


def _available_drives() -> list[str]:
    drives: list[str] = []
    if psutil:
        try:
            for part in psutil.disk_partitions(all=False):
                mount = part.mountpoint
                if os.path.exists(mount):
                    drives.append(mount)
        except Exception:
            pass
    if not drives:
        for drive in ("C:\\", "D:\\", "E:\\", "F:\\", "G:\\"):
            if os.path.exists(drive):
                drives.append(drive)
    # keep order + unique
    uniq: list[str] = []
    for item in drives:
        if item not in uniq:
            uniq.append(item)
    return uniq


def _iter_search_paths(search_path: str | None) -> list[str]:
    if search_path:
        return [search_path]
    return _available_drives()


def _walk_files(search_path: str):
    for root, dirs, files in os.walk(search_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        for file_name in files:
            yield root, file_name


def _word_match(query: str, file_name: str, root: str) -> bool:
    query = query.strip().lower()
    if not query:
        return True
    file_name_lower = file_name.lower()
    root_lower = root.lower()
    if query in file_name_lower or query in root_lower:
        return True
    words = [w for w in query.split() if len(w) >= 2]
    if not words:
        return False
    return all((w in file_name_lower or w in root_lower) for w in words)


def find_files(filename: str, search_path: str | None = None, max_results: int = 20) -> list[str]:
    results: list[str] = []
    query = filename.lower().strip()

    for base_path in _iter_search_paths(search_path):
        if not os.path.exists(base_path):
            continue
        try:
            for root, file_name in _walk_files(base_path):
                if _word_match(query, file_name, root):
                    results.append(str(Path(root) / file_name))
                    if len(results) >= max_results:
                        return results
        except Exception:
            continue
    return results


def find_by_extension(extension: str, search_path: str | None = None, max_results: int = 20) -> list[str]:
    ext = extension if extension.startswith(".") else f".{extension}"
    ext = ext.lower()
    results: list[str] = []

    for base_path in _iter_search_paths(search_path):
        if not os.path.exists(base_path):
            continue
        try:
            for root, file_name in _walk_files(base_path):
                if file_name.lower().endswith(ext):
                    results.append(str(Path(root) / file_name))
                    if len(results) >= max_results:
                        return results
        except Exception:
            continue
    return results


def find_photos(query: str, search_path: str | None = None, max_results: int = 20) -> list[str]:
    query_lower = query.lower().strip()
    results: list[str] = []

    # first pass: common media folders
    preferred_subdirs = ("pictures", "photos", "dcim", "downloads", "desktop")
    for base_path in _iter_search_paths(search_path):
        if not os.path.exists(base_path):
            continue
        try:
            for root, file_name in _walk_files(base_path):
                suffix = Path(file_name).suffix.lower()
                if suffix not in PHOTO_EXTENSIONS:
                    continue
                if preferred_subdirs and not any(tag in root.lower() for tag in preferred_subdirs):
                    continue
                if not _word_match(query_lower, file_name, root):
                    continue
                full_path = str(Path(root) / file_name)
                if full_path not in results:
                    results.append(full_path)
                if len(results) >= max_results:
                    return results
        except Exception:
            continue

    # second pass: full disk
    for base_path in _iter_search_paths(search_path):
        if not os.path.exists(base_path):
            continue
        try:
            for root, file_name in _walk_files(base_path):
                suffix = Path(file_name).suffix.lower()
                if suffix not in PHOTO_EXTENSIONS:
                    continue
                if not _word_match(query_lower, file_name, root):
                    continue
                full_path = str(Path(root) / file_name)
                if full_path not in results:
                    results.append(full_path)
                if len(results) >= max_results:
                    return results
        except Exception:
            continue
    return results


def find_documents(query: str, search_path: str | None = None, max_results: int = 20) -> list[str]:
    query_lower = query.lower().strip()
    results: list[str] = []
    for base_path in _iter_search_paths(search_path):
        if not os.path.exists(base_path):
            continue
        try:
            for root, file_name in _walk_files(base_path):
                suffix = Path(file_name).suffix.lower()
                if suffix not in DOCUMENT_EXTENSIONS:
                    continue
                if not _word_match(query_lower, file_name, root):
                    continue
                results.append(str(Path(root) / file_name))
                if len(results) >= max_results:
                    return results
        except Exception:
            continue
    return results
