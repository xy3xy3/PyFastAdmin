"""Redis 连接服务。"""

from __future__ import annotations

import asyncio
from typing import Any

from redis.asyncio import Redis

from app.config import REDIS_URL

_redis_client: Any = None
_redis_lock = asyncio.Lock()


async def get_redis() -> Any:
    """获取进程级 Redis 客户端（懒加载单例）。"""

    global _redis_client
    if _redis_client is not None:
        return _redis_client

    async with _redis_lock:
        if _redis_client is None:
            _redis_client = Redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 客户端连接。"""

    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
    _redis_client = None
