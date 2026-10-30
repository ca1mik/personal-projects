from __future__ import annotations

from sqlalchemy import select

from src.models import UserPreference
from src.repositories.base import SQLAlchemyRepository


class UserPreferenceRepository(SQLAlchemyRepository):
    async def get_by_user(self, user_id: int) -> UserPreference | None:
        return await self.session.scalar(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )

    async def get_or_create(self, user_id: int) -> UserPreference:
        preference = await self.get_by_user(user_id)
        if preference:
            return preference

        preference = UserPreference(user_id=user_id)
        self.session.add(preference)
        await self.session.flush()
        return preference

    async def list_daily_checkin_enabled(self) -> list[UserPreference]:
        query = select(UserPreference).where(
            UserPreference.daily_checkin_enabled.is_(True)
        )
        return list(await self.session.scalars(query))

    async def list_due_for_checkin(self, *, hour_utc: int) -> list[UserPreference]:
        query = select(UserPreference).where(
            UserPreference.daily_checkin_enabled.is_(True),
            UserPreference.checkin_hour_utc == hour_utc,
        )
        return list(await self.session.scalars(query))
