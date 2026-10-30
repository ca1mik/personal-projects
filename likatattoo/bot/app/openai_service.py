from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI, BadRequestError

from .config import Config


@dataclass(frozen=True)
class GeneratedTattooSketch:
    image_path: Path
    final_prompt: str
    model: str


class SketchBriefError(ValueError):
    pass


class SketchGenerationError(RuntimeError):
    pass


class TattooSketchService:
    _DISALLOWED_BRIEF_HINTS: tuple[str, ...] = (
        "photorealistic",
        "realistic photo",
        "photo render",
        "selfie",
        "passport",
        "id card",
        "driver license",
        "screenshot",
        "ui mockup",
        "website mockup",
        "app screen",
        "nude",
        "explicit sex",
        "фотореалист",
        "реалистичное фото",
        "селфи",
        "паспорт",
        "водительск",
        "скриншот",
        "интерфейс",
        "мокап",
        "сайт",
        "экран приложения",
        "обнажен",
        "секс",
        "эротик",
    )

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.client = AsyncOpenAI(
            api_key=cfg.openai_api_key,
            base_url=cfg.openai_base_url or None,
        )

    @staticmethod
    def _normalize_brief(brief: str) -> str:
        clean_brief = " ".join(brief.split()).strip()
        if not clean_brief:
            raise SketchBriefError("Tattoo brief cannot be empty.")
        if len(clean_brief) > 700:
            raise SketchBriefError("Tattoo brief is too long.")
        lowered = clean_brief.casefold()
        if any(hint in lowered for hint in TattooSketchService._DISALLOWED_BRIEF_HINTS):
            raise SketchBriefError(
                "Опиши именно тату-эскиз: без фото, документов, интерфейсов, мокапов на теле и NSFW."
            )
        return clean_brief

    def build_prompt(self, brief: str) -> str:
        clean_brief = self._normalize_brief(brief)
        return (
            "Create a tattoo sketch concept for a professional tattoo artist. "
            "This tool is only for tattoo sketches, not photos, renders, mockups, posters, or UI. "
            "Return a single design on a pure white background. "
            "Use crisp linework, tattoo flash clarity, and a composition suitable for a stencil preview. "
            "Interpret every request as a tattoo-ready sketch concept. "
            "Do not show skin, hands, a mockup body, extra objects, background scenes, watermarks, or typography labels. "
            "Keep the image presentation clean and centered. "
            f"User brief: {clean_brief}"
        )

    def build_chatgpt_prompt(self, brief: str) -> str:
        clean_brief = self._normalize_brief(brief)
        return (
            "Ты помогаешь подготовить идею татуировки для реального мастера.\n"
            "Сначала коротко предложи 2-3 сильных визуальных направления.\n"
            "Если в этом чате доступна генерация изображений, сгенерируй 1-4 варианта tattoo concept image.\n"
            "Требования к изображениям: чистый белый фон, один эскиз в кадре, crisp linework, stencil/flash clarity, "
            "центрированная композиция, без кожи, рук, mockup body, лишних предметов, интерьера, watermark и текстовых подписей.\n"
            "Если пользователь приложит фото-референсы, используй их как ориентир по форме и настроению, но не копируй один в один.\n"
            "В конце кратко перечисли, что нужно передать мастеру: размер, место нанесения, black-and-grey или color.\n\n"
            f"Бриф клиента: {clean_brief}"
        )

    async def generate(self, user_id: int, brief: str) -> GeneratedTattooSketch:
        final_prompt = self.build_prompt(brief)
        try:
            result = await self.client.images.generate(
                model=self.cfg.openai_image_model,
                prompt=final_prompt,
                size=self.cfg.openai_image_size,
                quality=self.cfg.openai_image_quality,
                user=str(user_id),
            )
        except BadRequestError as error:
            detail = self._extract_error_detail(error)
            raise SketchGenerationError(detail) from error
        if not result.data or not result.data[0].b64_json:
            raise RuntimeError("OpenAI did not return image data.")
        b64_payload = result.data[0].b64_json
        image_bytes = base64.b64decode(b64_payload)

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        image_path = self.cfg.generated_dir / f"{timestamp}_{user_id}.png"
        image_path.write_bytes(image_bytes)

        return GeneratedTattooSketch(
            image_path=image_path,
            final_prompt=final_prompt,
            model=self.cfg.openai_image_model,
        )

    @staticmethod
    def _extract_error_detail(error: object) -> str:
        body = getattr(error, "body", None)
        if isinstance(body, dict):
            nested = body.get("error")
            if isinstance(nested, dict):
                message = nested.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
            message = body.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return str(error).strip() or "OpenAI rejected the image request."
