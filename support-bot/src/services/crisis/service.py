from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class CrisisDetection:
    is_crisis: bool
    reason: str | None = None


class CrisisService:
    PATTERNS: dict[str, tuple[str, ...]] = {
        "suicide": (
            "не хочу жить",
            "хочу умереть",
            "покончить с собой",
            "суицид",
            "уйти из жизни",
            "убить себя",
        ),
        "self_harm": (
            "порезать себя",
            "навредить себе",
            "самоповреж",
            "сделать себе больно",
            "вскрыть вены",
        ),
        "violence": (
            "меня бьют",
            "он меня бьет",
            "домашнее насилие",
            "угрожает мне",
            "избивает",
            "партнер меня бьет",
        ),
        "child_harm": (
            "ударить ребенка",
            "навредить ребенку",
            "убить ребенка",
            "сделать больно ребенку",
            "хочу причинить вред ребенку",
        ),
    }

    def detect(self, text: str) -> CrisisDetection:
        normalized = self._normalize(text)
        for reason, patterns in self.PATTERNS.items():
            if any(pattern in normalized for pattern in patterns):
                return CrisisDetection(is_crisis=True, reason=reason)
        return CrisisDetection(is_crisis=False)

    def build_response(self) -> str:
        return (
            "Мне важно отнестись к этому серьезно. Если тебе или ребенку сейчас "
            "может угрожать опасность, сразу обратись за живой срочной помощью.\n\n"
            "Экстренные контакты:\n"
            "112\n"
            "8-800-2000-122\n"
            "8-495-989-50-50\n\n"
            "Пожалуйста, свяжись с близким человеком или живым специалистом прямо сейчас."
        )

    def _normalize(self, text: str) -> str:
        text = text.lower().replace("ё", "е")
        text = re.sub(r"\s+", " ", text)
        return text.strip()
