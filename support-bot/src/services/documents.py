from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from hashlib import sha1
from pathlib import Path

from src.config.settings import Settings


@dataclass(frozen=True)
class LegalDocument:
    slug: str
    title: str
    path: Path
    content: str
    version: str
    public_url: str


class DocumentService:
    def __init__(self, settings: Settings, project_root: Path | None = None) -> None:
        self.settings = settings
        self.project_root = project_root or Path(__file__).resolve().parents[2]

    def _read_file(self, *parts: str) -> str:
        path = self.project_root.joinpath(*parts)
        return path.read_text(encoding="utf-8")

    def load_prompt(self, name: str) -> str:
        return self._read_file("prompts", name)

    def load_content(self, name: str) -> str:
        return self._read_file("content", name)

    def _make_version(self, content: str) -> str:
        return sha1(content.encode("utf-8")).hexdigest()[:12]

    def _resolve_legal_version(self, slug: str, content: str) -> str:
        if slug == "privacy" and self.settings.privacy_policy_version:
            return self.settings.privacy_policy_version
        if slug == "offer" and self.settings.offer_version:
            return self.settings.offer_version
        if slug == "disclaimer" and self.settings.disclaimer_version:
            return self.settings.disclaimer_version
        if self.settings.legal_doc_version:
            return self.settings.legal_doc_version
        return self._make_version(content)

    def get_legal_document(self, slug: str, filename: str, title: str) -> LegalDocument:
        content = self._read_file("legal", filename)
        version = self._resolve_legal_version(slug, content)
        return LegalDocument(
            slug=slug,
            title=title,
            path=self.project_root / "legal" / filename,
            content=content,
            version=version,
            public_url=f"{self.settings.public_legal_base_url}/{filename}",
        )

    @cached_property
    def legal_documents(self) -> dict[str, LegalDocument]:
        return {
            "privacy": self.get_legal_document(
                "privacy", "privacy_policy.md", "Политика конфиденциальности"
            ),
            "offer": self.get_legal_document("offer", "offer.md", "Оферта"),
            "disclaimer": self.get_legal_document(
                "disclaimer", "disclaimer.md", "Дисклеймер"
            ),
        }
