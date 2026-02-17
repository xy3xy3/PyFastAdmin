from __future__ import annotations

import pytest

from app.services import task_registry


@pytest.mark.unit
def test_register_periodic_task_and_consumer() -> None:
    task_registry.reset_registry()

    async def periodic_runner() -> None:
        return None

    async def queue_handler(_payload: dict[str, object], _meta: dict[str, object]) -> None:
        return None

    task_registry.register_periodic_task(
        key="periodic_demo",
        name="周期任务",
        interval_seconds=60,
        runner=periodic_runner,
        tags=["system", "system"],
        display_columns=[task_registry.DisplayColumn(key="a", label="A")],
    )
    task_registry.register_queue_consumer(
        key="consumer_demo",
        name="消费者",
        stream="stream_demo",
        group="group_demo",
        handler=queue_handler,
        tags=["demo"],
    )

    periodic = task_registry.list_periodic_tasks()
    consumers = task_registry.list_queue_consumers()

    assert len(periodic) == 1
    assert periodic[0].tags == ("system",)
    assert len(consumers) == 1
    assert consumers[0].stream == "stream_demo"


@pytest.mark.unit
def test_register_duplicate_key_raises() -> None:
    task_registry.reset_registry()

    async def periodic_runner() -> None:
        return None

    task_registry.register_periodic_task(
        key="same_key",
        name="任务1",
        interval_seconds=60,
        runner=periodic_runner,
    )

    with pytest.raises(ValueError):
        task_registry.register_periodic_task(
            key="same_key",
            name="任务2",
            interval_seconds=60,
            runner=periodic_runner,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolve_display_values_supports_async_provider() -> None:
    async def provider() -> dict[str, str]:
        return {"x": "1"}

    result = await task_registry.resolve_display_values(provider)
    assert result == {"x": "1"}
