"""Conservative automatic effort selection; never changes the selected model."""
import re

IMPORTANT = re.compile(
    r'/goal\b|\b(?:важн\w*|ответствен\w*|срочн\w*|проверь\w*|провер\w*|'
    r'исправ\w*|фикси\w*|почини\w*|додел\w*|разработ\w*|настро\w*|'
    r'установ\w*|автозапуск\w*|удал\w*|выключ\w*|перезагруз\w*|'
    r'отправ\w*|рассыл\w*|письм\w*|почт\w*|оплат\w*|деньг\w*|'
    r'безопас\w*|парол\w*|резерв\w*|договор\w*|медицин\w*|лекарств\w*|'
    r'код(?:а|е|ом)?|кп|баз[ауые]\s+данных|shutdown|reboot|delete|deploy|payment|important)\b',
    re.I,
)
CASUAL = re.compile(
    r'^(?:привет\w*|здравствуй\w*|спасибо\w*|благодарю|пока|доброе утро|'
    r'добрый (?:день|вечер)|как дела|как ты|hi|hello|thanks)[\s!?.😊🙂👋]*$'
    r'|^(?:расскажи|скажи|придумай)\s+(?:мне\s+)?(?:анекдот|шутку)\b'
    r'|^(?:открой|запусти|сверни)\s+(?:гугл|google|браузер|доту|dota(?:\s+2)?)[\s!?.]*$',
    re.I,
)


def choose_effort(prompt):
    # Classify the actual request, before adding the owner's profile and examples.
    text = prompt.strip()
    if IMPORTANT.search(text):
        return 'high', 'important_or_consequential'
    if len(text) <= 240 and CASUAL.search(text):
        return 'low', 'short_casual_request'
    return 'medium', 'default_or_uncertain'
