"""角色模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(Document):
    """角色。"""

    class PermissionItem(BaseModel):
        """角色权限项。"""

        resource: str = Field(..., min_length=2, max_length=64)
        action: str = Field(..., min_length=2, max_length=32)
        priority: int = Field(default=3, ge=1, le=5)
        status: Literal["enabled", "disabled"] = "enabled"
        owner: str = Field(default="", max_length=32)
        tags: list[str] = Field(default_factory=list)
        description: str = Field(default="", max_length=120)

    name: str = Field(..., min_length=2, max_length=32)
    slug: str = Field(..., min_length=2, max_length=32)
    status: Literal["enabled", "disabled"] = "enabled"
    description: str = Field(default="", max_length=120)
    permissions: list[PermissionItem] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "roles"
