"""async_tasks 模型（脚手架生成）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pymongo import IndexModel
from pydantic import Field


def utc_now() -> datetime:
    """返回 UTC 当前时间。"""

    return datetime.now(timezone.utc)


class AsyncTasksItem(Document):
    """async_tasks 数据模型。"""

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=200)
    status: Literal["enabled", "disabled"] = "enabled"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "async_tasks_items"
        indexes = [
            IndexModel([("name", 1)], name="idx_async_tasks_name"),
            IndexModel([("updated_at", -1)], name="idx_async_tasks_updated_at"),
        ]
