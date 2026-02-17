"""队列消费工作进程入口。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from app.db import close_db, init_db
from app.config import QUEUE_BLOCK_MS
from app.services import task_monitor_service
from app.services.queue_service import (
    ack_message,
    enqueue_task,
    ensure_stream_group,
    move_to_dead_letter,
    parse_stream_message,
    read_group_messages,
    resolve_dead_letter_stream,
    resolve_max_retries,
)
from app.services.redis_service import close_redis
from app.services.task_registry import QueueConsumerDefinition, list_queue_consumers
from app.tasks import load_builtin_tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _read_worker_identity() -> tuple[str, str]:
    """读取队列 worker 身份信息。"""

    worker_id = os.getenv("PFA_WORKER_ID", "queue-0")
    consumer_name = f"{worker_id}:{os.getpid()}"
    return worker_id, consumer_name


async def _handle_single_message(
    definition: QueueConsumerDefinition,
    *,
    worker_id: str,
    consumer_name: str,
    message_id: str,
    fields: dict[str, str],
) -> None:
    """执行单条消息消费与重试/死信处理。"""

    payload, retry_count, _ = parse_stream_message(fields)
    max_retries = resolve_max_retries(definition)
    start = time.perf_counter()

    try:
        await definition.handler(
            payload,
            {
                "stream": definition.stream,
                "group": definition.group,
                "message_id": message_id,
                "retry_count": retry_count,
            },
        )
        await ack_message(definition.stream, definition.group, message_id)
        await task_monitor_service.mark_consumer_result(
            definition.key,
            consumer_name=definition.name,
            stream=definition.stream,
            group=definition.group,
            worker_id=worker_id,
            status="success",
            message_id=message_id,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        return
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        error_message = str(exc)

    next_retry = retry_count + 1
    dead_lettered = next_retry > max_retries
    retried = False

    if dead_lettered:
        await move_to_dead_letter(
            resolve_dead_letter_stream(definition),
            original_stream=definition.stream,
            original_group=definition.group,
            message_id=message_id,
            payload=payload,
            error=error_message,
            retry_count=next_retry,
        )
        await ack_message(definition.stream, definition.group, message_id)
    else:
        retried = True
        await enqueue_task(
            definition.stream,
            payload,
            retry_count=next_retry,
            source_message_id=message_id,
        )
        await ack_message(definition.stream, definition.group, message_id)

    await task_monitor_service.mark_consumer_result(
        definition.key,
        consumer_name=definition.name,
        stream=definition.stream,
        group=definition.group,
        worker_id=worker_id,
        status="failed",
        message_id=message_id,
        duration_ms=int((time.perf_counter() - start) * 1000),
        error=error_message,
        retried=retried,
        dead_lettered=dead_lettered,
    )


async def _run_queue_worker() -> int:
    """运行队列消费 worker。"""

    await init_db()
    try:
        load_builtin_tasks()
        definitions = list_queue_consumers()
        worker_id, consumer_name = _read_worker_identity()

        if not definitions:
            logger.warning("未注册任何队列消费者，worker=%s 进入心跳空转", worker_id)

        for definition in definitions:
            await ensure_stream_group(definition.stream, definition.group)

        next_heartbeat = 0.0
        while True:
            now = time.monotonic()
            if now >= next_heartbeat:
                await task_monitor_service.set_worker_heartbeat("queue", worker_id)
                next_heartbeat = now + 10

            processed = False
            for definition in definitions:
                messages = await read_group_messages(
                    definition.stream,
                    definition.group,
                    consumer_name,
                    block_ms=max(QUEUE_BLOCK_MS, 100),
                    count=1,
                )
                if not messages:
                    continue

                processed = True
                for message_id, fields in messages:
                    await _handle_single_message(
                        definition,
                        worker_id=worker_id,
                        consumer_name=consumer_name,
                        message_id=message_id,
                        fields=fields,
                    )

            if not processed:
                await asyncio.sleep(0.2)
    finally:
        await close_redis()
        await close_db()


def main() -> int:
    """队列 worker 同步入口。"""

    try:
        return asyncio.run(_run_queue_worker())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
