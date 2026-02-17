"""Redis Streams 队列服务。"""

from __future__ import annotations

import json
from typing import Any

from redis.exceptions import ResponseError

from app.config import QUEUE_MAX_RETRIES
from app.services.redis_service import get_redis
from app.services.task_registry import QueueConsumerDefinition


def _json_dumps(value: dict[str, Any]) -> str:
    """序列化队列载荷。"""

    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _json_loads(value: str) -> dict[str, Any]:
    """反序列化队列载荷。"""

    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


async def enqueue_task(
    stream: str,
    payload: dict[str, Any],
    *,
    retry_count: int = 0,
    source_message_id: str = "",
    maxlen: int | None = 10000,
) -> str:
    """向 Redis Stream 投递消息。"""

    redis = await get_redis()
    fields = {
        "payload": _json_dumps(payload),
        "retry_count": str(max(retry_count, 0)),
        "source_message_id": source_message_id,
    }
    if maxlen is not None and maxlen > 0:
        return str(await redis.xadd(stream, fields, maxlen=maxlen, approximate=True))
    return str(await redis.xadd(stream, fields))


async def ensure_stream_group(stream: str, group: str) -> None:
    """确保消费组存在，不存在时自动创建。"""

    redis = await get_redis()
    try:
        await redis.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def read_group_messages(
    stream: str,
    group: str,
    consumer_name: str,
    *,
    block_ms: int,
    count: int = 1,
) -> list[tuple[str, dict[str, str]]]:
    """从指定消费组读取消息。"""

    redis = await get_redis()
    data = await redis.xreadgroup(
        groupname=group,
        consumername=consumer_name,
        streams={stream: ">"},
        count=max(count, 1),
        block=max(block_ms, 1),
    )

    messages: list[tuple[str, dict[str, str]]] = []
    for _, stream_messages in data:
        for message_id, fields in stream_messages:
            normalized_fields = {str(k): str(v) for k, v in fields.items()}
            messages.append((str(message_id), normalized_fields))
    return messages


async def ack_message(stream: str, group: str, message_id: str) -> None:
    """确认消费成功消息。"""

    redis = await get_redis()
    await redis.xack(stream, group, message_id)


async def move_to_dead_letter(
    dead_letter_stream: str,
    *,
    original_stream: str,
    original_group: str,
    message_id: str,
    payload: dict[str, Any],
    error: str,
    retry_count: int,
) -> str:
    """写入死信流。"""

    redis = await get_redis()
    fields = {
        "payload": _json_dumps(payload),
        "error": error,
        "retry_count": str(max(retry_count, 0)),
        "original_stream": original_stream,
        "original_group": original_group,
        "original_message_id": message_id,
    }
    return str(await redis.xadd(dead_letter_stream, fields, maxlen=10000, approximate=True))


def parse_stream_message(fields: dict[str, str]) -> tuple[dict[str, Any], int, str]:
    """解析 Stream 消息字段。"""

    payload = _json_loads(str(fields.get("payload") or "{}"))
    source_message_id = str(fields.get("source_message_id") or "")
    try:
        retry_count = max(int(str(fields.get("retry_count") or "0")), 0)
    except (TypeError, ValueError):
        retry_count = 0
    return payload, retry_count, source_message_id


def resolve_max_retries(definition: QueueConsumerDefinition) -> int:
    """解析消费者重试次数。"""

    if definition.max_retries is None:
        return max(QUEUE_MAX_RETRIES, 0)
    return max(int(definition.max_retries), 0)


def resolve_dead_letter_stream(definition: QueueConsumerDefinition) -> str:
    """解析死信流名称。"""

    if definition.dead_letter_stream:
        return definition.dead_letter_stream
    return f"{definition.stream}:dead"
