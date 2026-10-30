from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from src.models import Consent
from src.repositories.base import SQLAlchemyRepository


class ConsentRepository(SQLAlchemyRepository):
    async def get_for_user(self, user_id: int) -> Consent | None:
        return await self.session.scalar(
            select(Consent).where(Consent.user_id == user_id)
        )

    async def get_or_create(self, user_id: int) -> Consent:
        consent = await self.get_for_user(user_id)
        if consent:
            return consent

        consent = Consent(user_id=user_id)
        self.session.add(consent)
        await self.session.flush()
        return consent

    async def accept_privacy(
        self, user_id: int, version: str, accepted_at: datetime
    ) -> Consent:
        consent = await self.get_or_create(user_id)
        consent.privacy_accepted = True
        consent.privacy_version = version
        consent.privacy_accepted_at = accepted_at
        consent.accepted_at = accepted_at
        await self.session.flush()
        return consent

    async def accept_offer(
        self, user_id: int, version: str, accepted_at: datetime
    ) -> Consent:
        consent = await self.get_or_create(user_id)
        consent.offer_accepted = True
        consent.offer_version = version
        consent.offer_accepted_at = accepted_at
        consent.accepted_at = accepted_at
        await self.session.flush()
        return consent

    async def accept_disclaimer(
        self, user_id: int, version: str, accepted_at: datetime
    ) -> Consent:
        consent = await self.get_or_create(user_id)
        consent.disclaimer_accepted = True
        consent.disclaimer_version = version
        consent.disclaimer_accepted_at = accepted_at
        consent.accepted_at = accepted_at
        await self.session.flush()
        return consent
