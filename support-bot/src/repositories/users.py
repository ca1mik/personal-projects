from __future__ import annotations

from sqlalchemy import select

from src.models import Platform, User
from src.repositories.base import SQLAlchemyRepository


class UserRepository(SQLAlchemyRepository):
    async def get_by_platform_user_id(
        self, platform: Platform | str, platform_user_id: str
    ) -> User | None:
        query = select(User).where(
            User.platform == str(platform),
            User.platform_user_id == platform_user_id,
        )
        return await self.session.scalar(query)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_or_create(
        self,
        *,
        platform: Platform | str,
        platform_user_id: str,
        username: str | None,
        first_name: str | None,
        email: str | None = None,
    ) -> User:
        user = await self.get_by_platform_user_id(platform, platform_user_id)
        if user:
            user.username = username
            user.first_name = first_name
            if email:
                user.email = email
            await self.session.flush()
            return user

        user = User(
            platform=str(platform),
            platform_user_id=platform_user_id,
            username=username,
            first_name=first_name,
            email=email,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def list_by_ids(self, user_ids: list[int]) -> list[User]:
        if not user_ids:
            return []
        query = select(User).where(User.id.in_(user_ids)).order_by(User.id.asc())
        return list(await self.session.scalars(query))
