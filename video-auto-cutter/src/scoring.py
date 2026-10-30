from __future__ import annotations

from dataclasses import dataclass
import re


VIRAL_KEYWORDS = (
    "ошибка",
    "почему",
    "секрет",
    "никто не говорит",
    "вот как",
    "главное",
    "запомни",
    "до",
    "после",
    "разбор",
    "миф",
    "результат",
)

CONVERSION_KEYWORDS = (
    "сохрани",
    "подпишись",
    "напиши",
    "консультация",
    "заявка",
    "разбор",
    "директ",
    "личку",
    "боль",
    "решение",
)

RETENTION_KEYWORDS = (
    "почему",
    "смотри",
    "вот",
    "запомни",
    "не делай",
    "главное",
    "сначала",
    "потом",
)

NEGATIVE_PATTERNS = (
    re.compile(r"\b(всем привет|сегодня поговорим|ээ+|эм+|ну|короче)\b", re.IGNORECASE),
    re.compile(r"\b(как бы|в общем|ну вот)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ClipScores:
    """Scoring bundle for a clip."""

    viral_score: int
    conversion_score: int
    retention_score: int
    tattoo_visual_score: int
    total_score: int
    reason: str

    def to_dict(self) -> dict[str, int | str]:
        return {
            "viral_score": self.viral_score,
            "conversion_score": self.conversion_score,
            "retention_score": self.retention_score,
            "tattoo_visual_score": self.tattoo_visual_score,
            "total_score": self.total_score,
            "reason": self.reason,
        }


def _keyword_score(text: str, keywords: tuple[str, ...], weight: int) -> int:
    return sum(weight for keyword in keywords if keyword in text)


def _negative_penalty(text: str) -> int:
    return sum(12 for pattern in NEGATIVE_PATTERNS if pattern.search(text))


def score_clip(
    text: str,
    duration: float,
    strategy: str = "balanced",
    tattoo_visual_score: float = 0.0,
) -> ClipScores:
    """Score a clip with viral, conversion, retention, and tattoo-visual heuristics."""
    lowered = text.lower().strip()
    words = [word for word in lowered.split() if word]
    density = len(words) / max(duration, 1.0)
    question_bonus = lowered.count("?") * 4
    exclamation_bonus = lowered.count("!") * 3
    digit_bonus = 8 if any(char.isdigit() for char in lowered) else 0
    opening_bonus = 10 if any(token in lowered[:90] for token in ("ошибка", "почему", "вот", "главное", "запомни")) else 0
    payoff_bonus = 8 if any(token in lowered for token in ("результат", "решение", "в итоге", "поэтому")) else 0
    penalty = _negative_penalty(lowered)

    viral = 34 + _keyword_score(lowered, VIRAL_KEYWORDS, 6) + question_bonus + exclamation_bonus + digit_bonus + opening_bonus - penalty
    conversion = 28 + _keyword_score(lowered, CONVERSION_KEYWORDS, 7) + payoff_bonus + digit_bonus - penalty
    retention = 32 + _keyword_score(lowered, RETENTION_KEYWORDS, 5) + min(int(density * 6), 20) + opening_bonus + question_bonus - penalty

    if 22 <= duration <= 42:
        retention += 6
    elif duration < 8 or duration > 60:
        retention -= 6

    if strategy == "aggressive":
        viral += 7
        retention += 4
    elif strategy == "expert":
        conversion += 6
        viral -= 2

    viral = max(0, min(100, int(round(viral))))
    conversion = max(0, min(100, int(round(conversion))))
    retention = max(0, min(100, int(round(retention))))
    visual = max(0, min(100, int(round(tattoo_visual_score))))

    total = max(
        0,
        min(
            100,
            int(round(viral * 0.28 + conversion * 0.22 + retention * 0.22 + visual * 0.28)),
        ),
    )

    reasons: list[str] = []
    if any(keyword in lowered for keyword in ("ошибка", "миф", "почему", "секрет")):
        reasons.append("strong hook language")
    if any(keyword in lowered for keyword in ("сохрани", "подпишись", "напиши", "разбор")):
        reasons.append("clear conversion trigger")
    if density >= 2.2:
        reasons.append("high speech density")
    if visual >= 65:
        reasons.append("strong tattoo visuals")
    if not reasons:
        reasons.append("balanced useful fragment")

    return ClipScores(
        viral_score=viral,
        conversion_score=conversion,
        retention_score=retention,
        tattoo_visual_score=visual,
        total_score=total,
        reason=" + ".join(reasons),
    )
