from __future__ import annotations


OVERLAYS = {
    "before": ["BEFORE", "ПРОЦЕСС: СТАРТ", "ОТ ЭСКИЗА ДО КОЖИ"],
    "process": ["PROCESS", "ПРОЦЕСС", "TATTOO SESSION"],
    "closeup": ["DETAILS", "ДЕТАЛИ", "DETAILS MATTER"],
    "linework": ["LINEWORK", "ЛАЙНВОРК", "PROCESS"],
    "shading": ["SHADING", "ТЕНИ", "DETAILS"],
    "after": ["AFTER", "ФИНАЛ", "FINAL RESULT"],
    "portfolio": ["PORTFOLIO", "ФИНАЛ", "DETAILS MATTER"],
    "story": ["today's session", "process", "booking open"],
}

CAPTIONS = {
    "tattoo_process": [
        "Немного процесса с сеанса ✦",
        "Фрагмент сессии: от линии к объёму.",
        "Детали, которые собирают работу в цельную картинку.",
    ],
    "closeup": [
        "Детали решают характер работы.",
        "Крупный план процесса и текстуры.",
    ],
    "satisfying": [
        "Ритм процесса, который хочется пересматривать.",
        "Тот самый satisfying-фрагмент с сессии.",
    ],
    "portfolio": [
        "Чистый портфолио-фрагмент работы.",
        "Финальный вид и детали татуировки.",
    ],
    "before_after": [
        "От эскиза к финалу за один короткий ролик.",
        "Before / Process / After с одной сессии.",
    ],
    "story": [
        "Немного процесса со свежего сеанса.",
        "Сегодняшняя сессия в нескольких секундах.",
    ],
}


def generate_tattoo_overlay(segment_type: str, strategy: str = "balanced") -> str:
    """Pick a short overlay text for a tattoo clip."""
    variants = OVERLAYS.get(segment_type, OVERLAYS["process"])
    if strategy == "expert" and len(variants) > 1:
        return variants[1]
    if strategy == "aggressive" and len(variants) > 2:
        return variants[-1]
    return variants[0]


def generate_tattoo_caption(clip_type: str, source_name: str, strategy: str = "balanced") -> str:
    """Generate a tattoo-oriented caption."""
    variants = CAPTIONS.get(clip_type, CAPTIONS["tattoo_process"])
    base = variants[0] if strategy != "expert" else variants[-1]
    tail = {
        "balanced": "Сохрани, если нравится такой стиль.",
        "aggressive": "Хочешь такой стиль — напиши в директ.",
        "expert": "На консультацию — в личку.",
    }[strategy]
    return f"{base}\n\nИсточник: {source_name}\n{tail}".strip()


def generate_tattoo_hashtags(max_tags: int = 12) -> list[str]:
    """Return curated tattoo hashtags."""
    tags = [
        "#tattoo",
        "#tattooprocess",
        "#tattooartist",
        "#ink",
        "#linework",
        "#shading",
        "#tattooreels",
        "#tattoostyle",
        "#tattoodetails",
        "#tattooportfolio",
        "#tattooideas",
        "#freshink",
    ]
    return tags[:max_tags]
