from __future__ import annotations

from functools import lru_cache

from src.config import get_settings
from src.services.container import AppContainer, build_container


@lru_cache(maxsize=1)
def get_scheduler_container() -> AppContainer:
    return build_container(get_settings())
