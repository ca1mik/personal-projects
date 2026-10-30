from __future__ import annotations

from aiogram.types import LabeledPrice

from .config import Config, GenerationPack, ServiceOffer


def find_pack(cfg: Config, code: str) -> GenerationPack | None:
    for pack in cfg.generation_packs:
        if pack.code == code:
            return pack
    return None


def pack_prices(pack: GenerationPack) -> list[LabeledPrice]:
    return [LabeledPrice(label=pack.title, amount=pack.price_xtr)]


def find_service_offer(cfg: Config, code: str) -> ServiceOffer | None:
    for offer in cfg.service_offers:
        if offer.code == code:
            return offer
    return None


def service_prices(offer: ServiceOffer) -> list[LabeledPrice]:
    return [LabeledPrice(label=offer.title, amount=offer.amount_rub * 100)]


def service_offer_checkout_description(offer: ServiceOffer) -> str:
    if offer.code == "portfolio":
        return "Оплата расходников для портфолио-сеанса"
    return "Предоплата за сеанс татуировки"
