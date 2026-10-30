from __future__ import annotations

from .scoring import ClipScores


def generate_cta(
    text: str,
    clip_type: str,
    language: str = "ru",
    strategy: str = "balanced",
) -> list[str]:
    """Generate CTA options for a clip."""
    del language
    text_lower = text.lower()
    ctas = [
        "Сохрани, чтобы не потерять",
        "Подпишись, если хочешь больше таких разборов",
        "Напиши «разбор» — скину подробности",
        "Скинь это тому, кому сейчас актуально",
        "Если нужен полный разбор — напиши в личку",
        "Напиши в комментариях, было ли у тебя так",
    ]

    if clip_type == "tattoo":
        ctas = [
            "Записаться — в личные сообщения",
            "Хочешь такой стиль — напиши в директ",
            "Сохрани идею для будущей тату",
            "Больше работ — в профиле",
            "На консультацию — в личку",
        ]

    if "система" in text_lower:
        ctas.insert(0, "Хочешь такую же систему — напиши «система»")

    if strategy == "expert":
        ctas = [
            "Если нужен полный разбор — напиши в личку",
            "Подпишись, если хочешь больше практических разборов",
            "Сохрани, чтобы вернуться к этому позже",
        ] + ctas
    elif strategy == "aggressive":
        ctas = [
            "Не откладывай — сохрани это сейчас",
            "Если хочешь результат — напиши «разбор»",
        ] + ctas

    unique: list[str] = []
    for cta in ctas:
        if cta not in unique:
            unique.append(cta)
    return unique


def choose_cta(text: str, scores: ClipScores, strategy: str = "balanced") -> str:
    """Choose the most suitable CTA."""
    ctas = generate_cta(text, clip_type="short", strategy=strategy)
    if scores.conversion_score >= 75:
        for cta in ctas:
            if "напиши" in cta.lower() or "лич" in cta.lower():
                return cta
    if scores.viral_score >= 75:
        for cta in ctas:
            if "сохрани" in cta.lower() or "скинь" in cta.lower():
                return cta
    return ctas[0]
