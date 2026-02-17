"""queue_consumers 模型（脚手架生成）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pymongo import IndexModel
from pydantic import Field


def utc_now() -> datetime:
    """返回 UTC 当前时间。"""

    return datetime.now(timezone.utc)


class QueueConsumersItem(Document):
    """queue_consumers 数据模型。"""

    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=200)
    status: Literal["enabled", "disabled"] = "enabled"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "queue_consumers_items"
        indexes = [
            IndexModel([("name", 1)], name="idx_queue_consumers_name"),
            IndexModel([("updated_at", -1)], name="idx_queue_consumers_updated_at"),
        ]
