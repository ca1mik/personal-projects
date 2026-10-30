from src.services.crisis import CrisisService


def test_crisis_service_detects_suicide_keywords() -> None:
    service = CrisisService()
    result = service.detect("Иногда мне кажется, что я не хочу жить и хочу исчезнуть.")
    assert result.is_crisis is True
    assert result.reason == "suicide"


def test_crisis_service_ignores_non_crisis_text() -> None:
    service = CrisisService()
    result = service.detect("Сегодня просто очень устала и хочу выспаться.")
    assert result.is_crisis is False
    assert result.reason is None
