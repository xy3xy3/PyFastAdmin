"""RBAC 权限模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RbacPermission(Document):
    """角色权限条目。"""

    role_slug: str = Field(..., min_length=2, max_length=32)
    resource: str = Field(..., min_length=2, max_length=64)
    action: str = Field(..., min_length=2, max_length=32)
    priority: int = Field(default=3, ge=1, le=5)
    status: Literal["enabled", "disabled"] = "enabled"
    owner: str = Field(default="", max_length=32)
    tags: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=120)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "rbac_permissions"
