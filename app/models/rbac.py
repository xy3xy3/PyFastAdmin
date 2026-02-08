"""RBAC 权限模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RbacPolicy(Document):
    """RBAC 权限条目（角色-资源-动作）。"""

    role_key: str = Field(..., min_length=2, max_length=32)
    role_name: str = Field(..., min_length=2, max_length=64)
    resource: str = Field(..., min_length=2, max_length=64)
    action: str = Field(..., min_length=2, max_length=32)
    owner: str = Field(..., min_length=2, max_length=32)
    priority: int = Field(default=3, ge=1, le=5)
    status: Literal["enabled", "disabled", "archived"] = "enabled"
    tags: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=240)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "rbac_policies"
