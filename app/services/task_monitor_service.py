"""异步任务监控数据服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import WORKER_HEARTBEAT_TTL_SECONDS
from app.services.redis_service import get_redis

PERIODIC_MONITOR_PREFIX = "pfa:monitor:periodic:"
CONSUMER_MONITOR_PREFIX = "pfa:monitor:consumer:"
HEARTBEAT_PREFIX = "pfa:heartbeat:"


def utc_now_iso() -> str:
    """返回当前 UTC 时间字符串。"""

    return datetime.now(timezone.utc).isoformat()


def periodic_monitor_key(task_key: str) -> str:
    """构造周期任务监控键。"""

    return f"{PERIODIC_MONITOR_PREFIX}{task_key}"


def consumer_monitor_key(consumer_key: str) -> str:
    """构造队列消费者监控键。"""

    return f"{CONSUMER_MONITOR_PREFIX}{consumer_key}"


def heartbeat_key(worker_type: str, worker_id: str) -> str:
    """构造进程心跳键。"""

    return f"{HEARTBEAT_PREFIX}{worker_type}:{worker_id}"


async def set_worker_heartbeat(worker_type: str, worker_id: str) -> None:
    """写入进程心跳。"""

    redis = await get_redis()
    await redis.set(
        heartbeat_key(worker_type, worker_id),
        utc_now_iso(),
        ex=max(WORKER_HEARTBEAT_TTL_SECONDS, 10),
    )


async def get_worker_heartbeats(worker_type: str) -> dict[str, str]:
    """读取指定类型的全部存活心跳。"""

    try:
        redis = await get_redis()
        pattern = heartbeat_key(worker_type, "*")
        keys = await redis.keys(pattern)
        if not keys:
            return {}

        values = await redis.mget(keys)
    except Exception:
        return {}

    result: dict[str, str] = {}
    for key, value in zip(keys, values):
        worker_id = str(key).split(f"{worker_type}:", 1)[-1]
        result[worker_id] = str(value or "")
    return result


async def get_periodic_monitor(task_key: str) -> dict[str, str]:
    """读取周期任务监控记录。"""

    try:
        redis = await get_redis()
        payload = await redis.hgetall(periodic_monitor_key(task_key))
    except Exception:
        return {}
    return {k: str(v) for k, v in payload.items()}


async def get_consumer_monitor(consumer_key: str) -> dict[str, str]:
    """读取队列消费者监控记录。"""

    try:
        redis = await get_redis()
        payload = await redis.hgetall(consumer_monitor_key(consumer_key))
    except Exception:
        return {}
    return {k: str(v) for k, v in payload.items()}


async def mark_periodic_started(task_key: str, *, task_name: str, worker_id: str) -> None:
    """记录周期任务开始执行状态。"""

    redis = await get_redis()
    now = utc_now_iso()
    await redis.hset(
        periodic_monitor_key(task_key),
        mapping={
            "key": task_key,
            "name": task_name,
            "last_status": "running",
            "last_error": "",
            "last_started_at": now,
            "worker_id": worker_id,
            "updated_at": now,
        },
    )


async def mark_periodic_finished(
    task_key: str,
    *,
    task_name: str,
    worker_id: str,
    status: str,
    duration_ms: int,
    next_run_at: str,
    error: str = "",
) -> None:
    """记录周期任务执行结果。"""

    redis = await get_redis()
    now = utc_now_iso()
    monitor_key = periodic_monitor_key(task_key)

    await redis.hset(
        monitor_key,
        mapping={
            "key": task_key,
            "name": task_name,
            "last_status": status,
            "last_error": error,
            "last_finished_at": now,
            "last_duration_ms": str(max(duration_ms, 0)),
            "next_run_at": next_run_at,
            "worker_id": worker_id,
            "updated_at": now,
        },
    )
    await redis.hincrby(monitor_key, "run_count", 1)
    if status == "success":
        await redis.hincrby(monitor_key, "success_count", 1)
    else:
        await redis.hincrby(monitor_key, "failure_count", 1)


async def mark_consumer_result(
    consumer_key: str,
    *,
    consumer_name: str,
    stream: str,
    group: str,
    worker_id: str,
    status: str,
    message_id: str,
    duration_ms: int,
    error: str = "",
    retried: bool = False,
    dead_lettered: bool = False,
) -> None:
    """记录队列消费者执行结果。"""

    redis = await get_redis()
    now = utc_now_iso()
    monitor_key = consumer_monitor_key(consumer_key)

    await redis.hset(
        monitor_key,
        mapping={
            "key": consumer_key,
            "name": consumer_name,
            "stream": stream,
            "group": group,
            "last_status": status,
            "last_error": error,
            "last_message_id": message_id,
            "last_run_at": now,
            "last_duration_ms": str(max(duration_ms, 0)),
            "worker_id": worker_id,
            "updated_at": now,
        },
    )
    await redis.hincrby(monitor_key, "consume_count", 1)
    if status == "success":
        await redis.hincrby(monitor_key, "success_count", 1)
    else:
        await redis.hincrby(monitor_key, "failure_count", 1)

    if retried:
        await redis.hincrby(monitor_key, "retry_count", 1)
    if dead_lettered:
        await redis.hincrby(monitor_key, "dead_letter_count", 1)


async def get_stream_group_pending(stream: str, group: str) -> int:
    """读取消费组待处理数量。"""

    redis = await get_redis()
    try:
        data = await redis.xpending(stream, group)
    except Exception:
        return 0

    # redis-py 可能返回 dict 或 tuple，兼容处理。
    if isinstance(data, dict):
        return int(data.get("pending", 0))
    if isinstance(data, (tuple, list)) and data:
        try:
            return int(data[0])
        except (TypeError, ValueError):
            return 0
    return 0
