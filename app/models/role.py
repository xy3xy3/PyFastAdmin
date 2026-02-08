"""角色模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(Document):
    """角色。"""

    name: str = Field(..., min_length=2, max_length=32)
    slug: str = Field(..., min_length=2, max_length=32)
    status: Literal["enabled", "disabled"] = "enabled"
    description: str = Field(default="", max_length=120)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "roles"
