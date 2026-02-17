"""数据库初始化与连接管理。"""

from __future__ import annotations

from typing import Any, cast

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from .config import MONGO_DB, MONGO_URL
from .models import AdminUser, Role, ConfigItem, OperationLog, BackupRecord, AsyncTasksItem, QueueConsumersItem

_mongo_client: AsyncIOMotorClient | None = None


async def init_db() -> None:
    """初始化 Beanie，并保留客户端用于关闭。"""
    global _mongo_client
    _mongo_client = AsyncIOMotorClient(MONGO_URL)
    await init_beanie(
        # Motor 与 Beanie 的类型标注来源不同，这里显式转换避免类型检查误报。
        database=cast(Any, _mongo_client[MONGO_DB]),
        document_models=[Role, AdminUser, ConfigItem, OperationLog, BackupRecord, AsyncTasksItem, QueueConsumersItem],
    )


async def close_db() -> None:
    """关闭 Mongo 连接。"""
    if _mongo_client is not None:
        _mongo_client.close()
