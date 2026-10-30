from __future__ import annotations


def generate_hooks(
    text: str,
    max_hooks: int = 5,
    language: str = "ru",
    strategy: str = "balanced",
) -> list[str]:
    """Generate heuristic hook variants from clip text."""
    del language
    preview = " ".join(text.strip().split()[:7]).strip() or "эту мысль"
    hooks = [
        "Главная ошибка, из-за которой нет результата",
        f"Вот почему у тебя не получается {preview}".strip(),
        "Запомни эту мысль",
        "Не делай это, пока не понял главное",
        "Если хочешь результат — начни с этого",
        "Большинство сливает именно здесь",
        "Это меняет весь подход",
    ]

    if strategy == "expert":
        hooks = [
            "Ключевая мысль, которую часто упускают",
            "Я бы не делал следующий шаг, пока не понял это",
            "Вот что реально влияет на результат",
            "Сначала разберись в этом принципе",
        ] + hooks
    elif strategy == "aggressive":
        hooks = [
            "Большинство делает это неправильно",
            "Вот где все теряют результат",
            "Если досмотришь до конца, поймёшь почему",
        ] + hooks

    unique: list[str] = []
    for hook in hooks:
        if hook not in unique:
            unique.append(hook)
        if len(unique) >= max_hooks:
            break
    return unique


def choose_best_hook(hooks: list[str], text: str, strategy: str = "balanced") -> str:
    """Choose the best hook variant for the clip."""
    if not hooks:
        return ""

    lowered = text.lower()
    prioritized: list[tuple[int, str]] = []
    for hook in hooks:
        score = 0
        hook_lower = hook.lower()
        if "ошибка" in hook_lower and "ошибка" in lowered:
            score += 4
        if "почему" in hook_lower and "почему" in lowered:
            score += 4
        if "результат" in hook_lower and "результат" in lowered:
            score += 3
        if strategy == "expert" and ("ключевая" in hook_lower or "принцип" in hook_lower):
            score += 3
        if strategy == "aggressive" and ("не делай" in hook_lower or "теряют" in hook_lower):
            score += 3
        prioritized.append((score, hook))

    prioritized.sort(key=lambda item: (-item[0], len(item[1])))
    return prioritized[0][1]
