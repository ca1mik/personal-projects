from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.config import load_config
from app.openai_service import SketchBriefError, TattooSketchService


def test_service_passes_optional_base_url_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_async_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(images=SimpleNamespace())

    monkeypatch.setattr("app.openai_service.AsyncOpenAI", fake_async_openai)
    cfg = load_config()
    cfg = cfg.__class__(**{**cfg.__dict__, "openai_base_url": "https://codex.sale/v1"})

    TattooSketchService(cfg)

    assert captured["api_key"] == cfg.openai_api_key
    assert captured["base_url"] == "https://codex.sale/v1"


def test_build_prompt_trims_and_embeds_user_brief() -> None:
    service = TattooSketchService(load_config())
    prompt = service.build_prompt("  thin snake   around moon  ")

    assert "thin snake around moon" in prompt
    assert "  " not in prompt


def test_build_prompt_rejects_empty_brief() -> None:
    service = TattooSketchService(load_config())

    with pytest.raises(SketchBriefError):
        service.build_prompt("   ")


def test_build_prompt_rejects_non_sketch_requests() -> None:
    service = TattooSketchService(load_config())

    with pytest.raises(SketchBriefError):
        service.build_prompt("photorealistic selfie on skin")


def test_build_chatgpt_prompt_mentions_reference_and_images() -> None:
    service = TattooSketchService(load_config())

    prompt = service.build_chatgpt_prompt("black raven on branch")

    assert "ChatGPT" not in prompt
    assert "сгенерируй 1-4 варианта" in prompt
    assert "фото-референсы" in prompt
    assert "black raven on branch" in prompt


@pytest.mark.asyncio
async def test_generate_uses_supported_gpt_image_args(tmp_path: Path) -> None:
    cfg = load_config()
    cfg = cfg.__class__(**{**cfg.__dict__, "generated_dir": tmp_path})
    service = TattooSketchService(cfg)
    captured: dict[str, object] = {}

    class FakeImages:
        async def generate(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                data=[SimpleNamespace(b64_json=base64.b64encode(b"png").decode("ascii"))]
            )

    service.client = cast(Any, SimpleNamespace(images=FakeImages()))
    result = await service.generate(77, "thin snake around moon")

    assert captured["model"] == cfg.openai_image_model
    assert captured["size"] == cfg.openai_image_size
    assert captured["quality"] == cfg.openai_image_quality
    assert captured["user"] == "77"
    assert "response_format" not in captured
    assert result.image_path.exists()


def test_extract_error_detail_prefers_api_message() -> None:
    detail = TattooSketchService._extract_error_detail(
        SimpleNamespace(body={"error": {"message": "Unsupported parameter: response_format"}})
    )
    assert detail == "Unsupported parameter: response_format"


def test_extract_error_detail_falls_back_to_string() -> None:
    class FakeBadRequest(Exception):
        body = None

        def __str__(self) -> str:
            return "Bad request"

    detail = TattooSketchService._extract_error_detail(FakeBadRequest())
    assert detail == "Bad request"
