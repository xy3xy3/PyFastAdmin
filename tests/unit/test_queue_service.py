from __future__ import annotations

from typing import Any

import pytest

from app.services import queue_service, task_registry


class FakeRedis:
    def __init__(self) -> None:
        self.xadd_calls: list[dict[str, Any]] = []

    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None, approximate: bool = False) -> str:
        self.xadd_calls.append(
            {
                "stream": stream,
                "fields": fields,
                "maxlen": maxlen,
                "approximate": approximate,
            }
        )
        return "1-0"


@pytest.mark.unit
def test_parse_stream_message_extracts_payload_and_retry_count() -> None:
    payload, retry_count, source_message_id = queue_service.parse_stream_message(
        {
            "payload": '{"event":"ok"}',
            "retry_count": "2",
            "source_message_id": "168-1",
        }
    )

    assert payload == {"event": "ok"}
    assert retry_count == 2
    assert source_message_id == "168-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_task_writes_stream_message(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()

    async def fake_get_redis() -> FakeRedis:
        return fake

    monkeypatch.setattr(queue_service, "get_redis", fake_get_redis)

    message_id = await queue_service.enqueue_task("test_stream", {"event": "created"}, retry_count=1)

    assert message_id == "1-0"
    assert fake.xadd_calls
    assert fake.xadd_calls[0]["stream"] == "test_stream"
    assert fake.xadd_calls[0]["fields"]["retry_count"] == "1"


@pytest.mark.unit
def test_resolve_dead_letter_stream_and_retry_count() -> None:
    async def handler(_payload: dict[str, Any], _meta: dict[str, Any]) -> None:
        return None

    definition = task_registry.QueueConsumerDefinition(
        key="k",
        name="n",
        stream="stream",
        group="group",
        handler=handler,
        max_retries=5,
        dead_letter_stream="dead_stream",
    )

    assert queue_service.resolve_max_retries(definition) == 5
    assert queue_service.resolve_dead_letter_stream(definition) == "dead_stream"
