"""内置队列消费者注册。"""

from __future__ import annotations

import logging
from typing import Any

from app.services import task_monitor_service
from app.services.queue_service import resolve_max_retries
from app.services.task_registry import DisplayColumn, register_queue_consumer

logger = logging.getLogger(__name__)


async def _handle_demo_event(payload: dict[str, Any], meta: dict[str, Any]) -> None:
    """消费示例事件消息。"""

    event_name = str(payload.get("event") or "unknown")
    logger.info("示例消费者收到事件=%s message_id=%s", event_name, meta.get("message_id"))


async def _demo_display_values() -> dict[str, str]:
    """返回示例消费者动态展示字段。"""

    pending = await task_monitor_service.get_stream_group_pending("pfa:queue:demo_events", "pfa_demo_group")
    max_retries = "0"
    if _DEMO_CONSUMER is not None:
        max_retries = str(resolve_max_retries(_DEMO_CONSUMER))
    return {
        "pending": str(pending),
        "max_retries": max_retries,
    }


def register_tasks() -> None:
    """注册内置队列消费者（幂等）。"""

    global _DEMO_CONSUMER
    try:
        _DEMO_CONSUMER = register_queue_consumer(
            key="demo_events_consumer",
            name="示例事件消费者",
            stream="pfa:queue:demo_events",
            group="pfa_demo_group",
            handler=_handle_demo_event,
            tags=["system", "demo"],
            display_columns=[
                DisplayColumn(key="pending", label="待处理"),
                DisplayColumn(key="max_retries", label="最大重试"),
            ],
            display_values_provider=_demo_display_values,
        )
    except ValueError:
        # 已注册时复用现有定义，保持 display provider 可继续读取重试上限。
        from app.services.task_registry import list_queue_consumers

        existing = next((item for item in list_queue_consumers() if item.key == "demo_events_consumer"), None)
        if existing is not None:
            _DEMO_CONSUMER = existing


_DEMO_CONSUMER = None
register_tasks()
