"""异步任务注册中心。"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Any, Awaitable, Callable

DisplayValueProvider = Callable[[], dict[str, Any] | Awaitable[dict[str, Any]]]
PeriodicRunner = Callable[[], Awaitable[None]]
QueueHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class DisplayColumn:
    """监控页面动态列定义。"""

    key: str
    label: str


@dataclass(frozen=True, slots=True)
class PeriodicTaskDefinition:
    """周期任务定义。"""

    key: str
    name: str
    interval_seconds: int
    runner: PeriodicRunner
    tags: tuple[str, ...] = ()
    display_columns: tuple[DisplayColumn, ...] = ()
    display_values_provider: DisplayValueProvider | None = None


@dataclass(frozen=True, slots=True)
class QueueConsumerDefinition:
    """队列消费者定义。"""

    key: str
    name: str
    stream: str
    group: str
    handler: QueueHandler
    tags: tuple[str, ...] = ()
    max_retries: int | None = None
    dead_letter_stream: str | None = None
    display_columns: tuple[DisplayColumn, ...] = ()
    display_values_provider: DisplayValueProvider | None = None


_periodic_tasks: dict[str, PeriodicTaskDefinition] = {}
_queue_consumers: dict[str, QueueConsumerDefinition] = {}


def _normalize_tags(raw_tags: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """清洗标签并保持顺序去重。"""

    tags: list[str] = []
    for item in raw_tags or []:
        value = str(item).strip()
        if not value or value in tags:
            continue
        tags.append(value)
    return tuple(tags)


def _normalize_columns(raw_columns: list[DisplayColumn] | tuple[DisplayColumn, ...] | None) -> tuple[DisplayColumn, ...]:
    """清洗动态列定义，避免重复 key。"""

    column_map: dict[str, DisplayColumn] = {}
    for column in raw_columns or []:
        key = str(column.key).strip()
        label = str(column.label).strip()
        if not key or not label or key in column_map:
            continue
        column_map[key] = DisplayColumn(key=key, label=label)
    return tuple(column_map.values())


def register_periodic_task(
    *,
    key: str,
    name: str,
    interval_seconds: int,
    runner: PeriodicRunner,
    tags: list[str] | tuple[str, ...] | None = None,
    display_columns: list[DisplayColumn] | tuple[DisplayColumn, ...] | None = None,
    display_values_provider: DisplayValueProvider | None = None,
) -> PeriodicTaskDefinition:
    """注册周期任务定义。"""

    normalized_key = str(key).strip()
    normalized_name = str(name).strip()
    if not normalized_key:
        raise ValueError("周期任务 key 不能为空")
    if not normalized_name:
        raise ValueError("周期任务 name 不能为空")
    if interval_seconds <= 0:
        raise ValueError("周期任务 interval_seconds 必须大于 0")
    if normalized_key in _periodic_tasks:
        raise ValueError(f"周期任务已注册: {normalized_key}")

    definition = PeriodicTaskDefinition(
        key=normalized_key,
        name=normalized_name,
        interval_seconds=int(interval_seconds),
        runner=runner,
        tags=_normalize_tags(tags),
        display_columns=_normalize_columns(display_columns),
        display_values_provider=display_values_provider,
    )
    _periodic_tasks[definition.key] = definition
    return definition


def register_queue_consumer(
    *,
    key: str,
    name: str,
    stream: str,
    group: str,
    handler: QueueHandler,
    tags: list[str] | tuple[str, ...] | None = None,
    max_retries: int | None = None,
    dead_letter_stream: str | None = None,
    display_columns: list[DisplayColumn] | tuple[DisplayColumn, ...] | None = None,
    display_values_provider: DisplayValueProvider | None = None,
) -> QueueConsumerDefinition:
    """注册 Redis Streams 消费者定义。"""

    normalized_key = str(key).strip()
    normalized_name = str(name).strip()
    normalized_stream = str(stream).strip()
    normalized_group = str(group).strip()

    if not normalized_key:
        raise ValueError("队列消费者 key 不能为空")
    if not normalized_name:
        raise ValueError("队列消费者 name 不能为空")
    if not normalized_stream:
        raise ValueError("队列消费者 stream 不能为空")
    if not normalized_group:
        raise ValueError("队列消费者 group 不能为空")
    if normalized_key in _queue_consumers:
        raise ValueError(f"队列消费者已注册: {normalized_key}")

    definition = QueueConsumerDefinition(
        key=normalized_key,
        name=normalized_name,
        stream=normalized_stream,
        group=normalized_group,
        handler=handler,
        tags=_normalize_tags(tags),
        max_retries=max_retries if max_retries is None else max(int(max_retries), 0),
        dead_letter_stream=(str(dead_letter_stream).strip() or None),
        display_columns=_normalize_columns(display_columns),
        display_values_provider=display_values_provider,
    )
    _queue_consumers[definition.key] = definition
    return definition


def list_periodic_tasks() -> list[PeriodicTaskDefinition]:
    """返回全部周期任务定义。"""

    return list(_periodic_tasks.values())


def list_queue_consumers() -> list[QueueConsumerDefinition]:
    """返回全部队列消费者定义。"""

    return list(_queue_consumers.values())


async def resolve_display_values(provider: DisplayValueProvider | None) -> dict[str, Any]:
    """执行动态列值回调并统一异常兜底。"""

    if provider is None:
        return {}

    try:
        result = provider()
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return {}

    if not isinstance(result, dict):
        return {}
    return result


def reset_registry() -> None:
    """重置注册中心（主要用于测试）。"""

    _periodic_tasks.clear()
    _queue_consumers.clear()
