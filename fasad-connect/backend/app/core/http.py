from __future__ import annotations

from urllib.parse import quote


def content_disposition(file_name: str) -> str:
    """Заголовок скачивания с именем файла по-русски.

    Значения HTTP-заголовков передаются в latin-1, а имена у нас кириллические
    («Бланк заказа З-0042.xlsx»), поэтому имя уходит в `filename*` по RFC 5987.
    Рядом остаётся ASCII-запасное имя: старые клиенты берут его и не спотыкаются.
    """
    quoted = quote(file_name, safe="")
    fallback = file_name.encode("ascii", "replace").decode("ascii").replace('"', "")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quoted}"
