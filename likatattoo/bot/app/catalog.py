from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class PortfolioCategory:
    slug: str
    title: str
    source_folders: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioPreview:
    category: PortfolioCategory
    files: tuple[Path, ...]


PORTFOLIO_CATEGORIES = (
    PortfolioCategory("fresh", "Свежие работы", ("fresh",)),
    PortfolioCategory("lettering", "Надписи", ("lettering",)),
    PortfolioCategory("minimalism", "Минимализм", ("minimalism", "minimal")),
    PortfolioCategory("graphics", "Графика", ("graphics", "graphic")),
    PortfolioCategory("characters", "Персонажи", ("characters",)),
    PortfolioCategory("color", "Цветные работы", ("color",)),
    PortfolioCategory("healed", "Зажившие работы", ("healed",)),
)


def _iter_media(folder: Path) -> tuple[Path, ...]:
    if not folder.exists():
        return ()
    files = [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES]
    files.sort(key=lambda item: item.name.lower())
    return tuple(files)


def get_portfolio_previews(portfolio_root: Path, limit_per_category: int = 4) -> tuple[PortfolioPreview, ...]:
    previews: list[PortfolioPreview] = []
    for category in PORTFOLIO_CATEGORIES:
        collected: list[Path] = []
        for folder_name in category.source_folders:
            collected.extend(_iter_media(portfolio_root / folder_name))
        files = tuple(collected[:limit_per_category])
        previews.append(PortfolioPreview(category=category, files=files))
    return tuple(previews)


def build_empty_portfolio_hint(portfolio_root: Path) -> str:
    return (
        "Пока в каталоге нет загруженных примеров работ.\n\n"
        f"Добавь фото в папки внутри:\n<code>{portfolio_root}</code>\n\n"
        "Поддерживаются файлы JPG, PNG и WEBP."
    )
