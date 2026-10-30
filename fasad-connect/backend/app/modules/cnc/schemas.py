from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.modules.shared.schemas import ORMModel


class CncMachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    controller: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        result = value.strip()
        if not result or "\n" in result or "\r" in result:
            raise ValueError("Machine name must be a single non-empty line")
        return result


class CncMachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    controller: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return CncMachineCreate.clean_name(value) if value is not None else None


class CncMachineRead(ORMModel):
    id: uuid.UUID
    name: str
    controller: str | None
    is_active: bool
    created_at: datetime


class CncGenerateRequest(BaseModel):
    machine_id: uuid.UUID | None = None


class CncJobRead(ORMModel):
    id: uuid.UUID
    order_id: uuid.UUID
    part_id: uuid.UUID | None
    machine_id: uuid.UUID | None
    machine_name: str
    postprocessor: str
    file_name: str
    file_path: str
    version: int
    created_at: datetime
    created_by: uuid.UUID | None
