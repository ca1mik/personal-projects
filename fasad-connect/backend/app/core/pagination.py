from __future__ import annotations

from typing import Any

from fastapi import Query
from pydantic import BaseModel, ConfigDict


class PageParams(BaseModel):
    page: int = 1
    size: int = 20

    model_config = ConfigDict(from_attributes=True)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def get_page_params(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PageParams:
    return PageParams(page=page, size=size)


def pagination_meta(
    total: int, params: PageParams, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "page": params.page,
        "size": params.size,
        "total": total,
        "pages": max((total + params.size - 1) // params.size, 1),
    }
    if extra:
        meta.update(extra)
    return meta
