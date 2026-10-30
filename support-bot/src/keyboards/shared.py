from __future__ import annotations

from src.services.platforms import Button


def start_buttons() -> list[list[Button]]:
    return [
        [Button(text="Попробовать бесплатно", action="start:free")],
        [Button(text="Что это", action="start:about")],
        [Button(text="Условия и приватность", action="start:legal")],
        [Button(text="Поддержка", action="start:support")],
    ]


def adult_confirmation_buttons() -> list[list[Button]]:
    return [
        [Button(text="Да, мне есть 18", action="adult:yes")],
        [Button(text="Нет", action="adult:no")],
    ]


def consent_buttons(
    *,
    slug: str,
    document_url: str | None = None,
    document_action: str | None = None,
) -> list[list[Button]]:
    document_button = (
        [Button(text="Открыть документ", url=document_url, kind="url")]
        if document_url
        else [Button(text="Открыть документ", action=document_action or f"legal:show:{slug}")]
    )
    return [
        document_button,
        [Button(text="Согласен", action=f"consent:{slug}:accept")],
        [Button(text="Не согласен", action=f"consent:{slug}:decline")],
    ]


def legal_document_buttons(*, use_urls: bool) -> list[list[Button]]:
    if use_urls:
        return []
    return [
        [Button(text="Политика конфиденциальности", action="legal:show:privacy")],
        [Button(text="Оферта", action="legal:show:offer")],
        [Button(text="Дисклеймер", action="legal:show:disclaimer")],
    ]


def checkin_buttons() -> list[list[Button]]:
    return [
        [Button(text="Да, получать чек-ин", action="checkin:yes")],
        [Button(text="Нет, не сейчас", action="checkin:no")],
    ]


def pricing_buttons(*, include_telegram_fallback: bool = False) -> list[list[Button]]:
    buttons = [
        [Button(text="Неделя поддержки", action="pay:yookassa:week")],
        [Button(text="Месяц рядом", action="pay:yookassa:month")],
        [Button(text="Квартал заботы", action="pay:yookassa:quarter")],
    ]
    if include_telegram_fallback:
        buttons.extend(
            [
                [
                    Button(
                        text="Оплатить в Telegram: неделя", action="pay:telegram:week"
                    )
                ],
                [
                    Button(
                        text="Оплатить в Telegram: месяц", action="pay:telegram:month"
                    )
                ],
                [
                    Button(
                        text="Оплатить в Telegram: квартал",
                        action="pay:telegram:quarter",
                    )
                ],
            ]
        )
    return buttons


def payment_link_buttons(
    payment_url: str,
    *,
    include_telegram_fallback: bool = False,
    plan_slug: str | None = None,
) -> list[list[Button]]:
    if payment_url.startswith("mock://payment/"):
        payment_id = payment_url.rsplit("/", maxsplit=1)[-1]
        buttons: list[list[Button]] = [
            [
                Button(
                    text="Подтвердить демо-оплату",
                    action=f"pay:mock:confirm:{payment_id}",
                )
            ]
        ]
    else:
        buttons = [
            [Button(text="Оплатить через ЮKassa", url=payment_url, kind="url")],
        ]
    if include_telegram_fallback and plan_slug:
        buttons.append(
            [Button(text="Оплатить в Telegram", action=f"pay:telegram:{plan_slug}")]
        )
    return buttons


def subscription_buttons() -> list[list[Button]]:
    return [
        [Button(text="Отменить автопродление", action="subscription:cancel_autorenew")],
        [Button(text="Сменить тариф", action="subscription:change_plan")],
        [Button(text="Запросить возврат", action="subscription:refund")],
        [Button(text="Удалить мои данные", action="subscription:delete_data")],
    ]
