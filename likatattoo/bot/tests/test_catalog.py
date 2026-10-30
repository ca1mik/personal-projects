from __future__ import annotations

from pathlib import Path

from app.catalog import get_portfolio_previews


def test_get_portfolio_previews_collects_alias_folders(tmp_path: Path) -> None:
    portfolio_root = tmp_path / "portfolio"
    (portfolio_root / "graphic").mkdir(parents=True)
    (portfolio_root / "minimal").mkdir(parents=True)
    (portfolio_root / "characters").mkdir(parents=True)

    (portfolio_root / "graphic" / "graphic-01.jpg").write_bytes(b"jpg")
    (portfolio_root / "minimal" / "minimal-01.jpg").write_bytes(b"jpg")
    (portfolio_root / "characters" / "character-01.jpg").write_bytes(b"jpg")

    previews = {preview.category.slug: preview for preview in get_portfolio_previews(portfolio_root)}

    assert len(previews["graphics"].files) == 1
    assert len(previews["minimalism"].files) == 1
    assert len(previews["characters"].files) == 1
