"""Статусы заявки: один список на всю систему.

Списков было три, и они разошлись. Правка заявки разрешала «Квалифицирована», а
карточка клиента такого кода не знала и печатала в плашку сырое `qualified` —
менеджер видел английское слово там, где ждал русское. Симметрично «Спам» знал
сервер, но не знал интерфейс.

Здесь сторож: любой новый статус обязан появиться сразу и в разрешённых кодах,
и в подписях, и во фронтовом словаре.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.modules.leads.schemas import LEAD_STATUSES
from app.modules.leads.statuses import (
    CLOSED_LEAD_STATUSES,
    LEAD_STATUS_LABELS,
    lead_status_label,
)

FRONTEND_LABELS = Path(__file__).resolve().parents[3] / "frontend" / "lib" / "labels.ts"
FRONTEND_ROOT = FRONTEND_LABELS.parents[1]


def test_every_allowed_status_has_a_russian_label():
    """Разрешён к вводу — значит его есть чем подписать."""
    missing = [code for code in LEAD_STATUSES if code not in LEAD_STATUS_LABELS]

    assert missing == [], f"нет русской подписи у статусов: {missing}"


def test_labels_do_not_describe_unknown_statuses():
    """И наоборот: подпись без кода — мусор, который никогда не покажется."""
    extra = [code for code in LEAD_STATUS_LABELS if code not in LEAD_STATUSES]

    assert extra == [], f"подписи без статуса: {extra}"


def test_closed_statuses_are_real_statuses():
    """«Заказа не будет» ставится только известным статусам."""
    unknown = sorted(CLOSED_LEAD_STATUSES - set(LEAD_STATUSES))

    assert unknown == [], f"закрывающие статусы вне списка: {unknown}"


def test_unknown_code_is_shown_as_is():
    """Чужой код показываем буквально, а не прячем за «Неизвестно».

    Менеджеру полезнее увидеть, что именно лежит в базе, и сказать об этом.
    """
    assert lead_status_label("что-то-своё") == "что-то-своё"
    assert lead_status_label(None) == ""
    assert lead_status_label("rejected") == "Отказ"


def test_frontend_knows_the_same_statuses():
    """Словарь во фронте не должен отставать от сервера.

    Читаем файл, а не импортируем: тест-раннера у фронтенда нет, а расхождение
    ловить надо — именно оно и привело к сырому «qualified» на экране.
    """
    if FRONTEND_LABELS.exists():
        source = FRONTEND_LABELS.read_text(encoding="utf-8")
        block = re.search(r"export const LEAD_STATUS_LABELS: LabelMap = \{(.*?)\};", source, re.S)
        assert block, "во фронте не нашёлся словарь LEAD_STATUS_LABELS"
        label_maps = [dict(re.findall(r"([a-z_]+):\s*['\"]([^'\"]+)['\"]", block.group(1)))]
    else:
        # В переносимой сборке TSX-исходников нет. Проверяем код, который
        # браузер действительно загружает для списка и карточки заявки.
        manifest = json.loads((FRONTEND_ROOT / ".next/app-build-manifest.json").read_text(encoding="utf-8"))
        label_maps = []
        for route in ("/leads/page", "/leads/[id]/page"):
            prefix = f"static/chunks/app/{route.strip('/').removesuffix('/page')}/page-"
            files = [name for name in manifest["pages"][route] if name.startswith(prefix)]
            assert len(files) == 1, f"не нашёл активный пакет страницы {route}"
            source = (FRONTEND_ROOT / ".next" / files[0]).read_text(encoding="utf-8")
            block = re.search(r'\blet [a-z]=\{(new:"[^"]+"(?:,[a-z_]+:"[^"]+")+?)\}', source)
            assert block, f"во фронте не нашёлся словарь статусов на {route}"
            label_maps.append(dict(re.findall(r'([a-z_]+):"([^"]+)"', block.group(1))))

    for labels in label_maps:
        assert labels == LEAD_STATUS_LABELS, (
            f"подписи фронта расходятся с сервером: {labels!r} != {LEAD_STATUS_LABELS!r}"
        )
