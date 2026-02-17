from __future__ import annotations

import uuid

import pytest

from app.services import queue_service
from app.services.redis_service import close_redis, get_redis


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_stream_queue_runtime_chain() -> None:
    """真实 Redis 下验证入队/消费/ACK 基础链路。"""

    redis = await get_redis()
    try:
        await redis.ping()
    except Exception:
        await close_redis()
        pytest.skip("Redis 不可用，跳过队列链路集成测试")

    stream = f"pfa:test:stream:{uuid.uuid4().hex}"
    group = f"pfa_test_group_{uuid.uuid4().hex[:8]}"

    await queue_service.ensure_stream_group(stream, group)
    message_id = await queue_service.enqueue_task(stream, {"event": "integration_created"})
    assert message_id

    messages = await queue_service.read_group_messages(
        stream,
        group,
        consumer_name="integration_consumer",
        block_ms=1000,
        count=1,
    )
    assert messages

    consumed_message_id, fields = messages[0]
    payload, retry_count, _ = queue_service.parse_stream_message(fields)

    assert consumed_message_id
    assert payload == {"event": "integration_created"}
    assert retry_count == 0

    await queue_service.ack_message(stream, group, consumed_message_id)
    await redis.delete(stream)
