"""周期任务调度服务。"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from app.services import task_monitor_service
from app.services.task_registry import PeriodicTaskDefinition, list_periodic_tasks

logger = logging.getLogger(__name__)


def _now() -> datetime:
    """返回当前 UTC 时间。"""

    return datetime.now(timezone.utc)


def _assign_tasks(
    tasks: list[PeriodicTaskDefinition],
    *,
    worker_index: int,
    worker_total: int,
) -> list[PeriodicTaskDefinition]:
    """按 worker 分片周期任务，避免重复执行。"""

    if worker_total <= 1:
        return tasks
    selected: list[PeriodicTaskDefinition] = []
    for index, definition in enumerate(tasks):
        if index % worker_total == worker_index:
            selected.append(definition)
    return selected


async def run_periodic_worker(*, worker_id: str, worker_index: int, worker_total: int) -> None:
    """运行周期任务工作进程。"""

    tasks = _assign_tasks(
        list_periodic_tasks(),
        worker_index=max(worker_index, 0),
        worker_total=max(worker_total, 1),
    )
    if not tasks:
        logger.warning("周期任务 worker=%s 未分配到任务，进入心跳空转", worker_id)

    next_run_at: dict[str, datetime] = {definition.key: _now() for definition in tasks}
    next_heartbeat = 0.0

    while True:
        now_ts = time.monotonic()
        if now_ts >= next_heartbeat:
            await task_monitor_service.set_worker_heartbeat("periodic", worker_id)
            next_heartbeat = now_ts + 10

        now = _now()
        for definition in tasks:
            schedule_at = next_run_at.get(definition.key, now)
            if now < schedule_at:
                continue

            started = time.perf_counter()
            await task_monitor_service.mark_periodic_started(
                definition.key,
                task_name=definition.name,
                worker_id=worker_id,
            )

            status = "success"
            error_message = ""
            try:
                await definition.runner()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                status = "failed"
                error_message = str(exc)
                logger.exception("周期任务执行失败: %s", definition.key)

            duration_ms = int((time.perf_counter() - started) * 1000)
            next_time = _now() + timedelta(seconds=max(definition.interval_seconds, 1))
            next_run_at[definition.key] = next_time
            await task_monitor_service.mark_periodic_finished(
                definition.key,
                task_name=definition.name,
                worker_id=worker_id,
                status=status,
                error=error_message,
                duration_ms=duration_ms,
                next_run_at=next_time.isoformat(),
            )

        await asyncio.sleep(0.5)


def read_worker_identity_from_env() -> tuple[str, int, int]:
    """从环境变量读取周期 worker 身份信息。"""

    worker_id = os.getenv("PFA_WORKER_ID", "periodic-0")

    try:
        worker_index = int(os.getenv("PFA_WORKER_INDEX", "0"))
    except ValueError:
        worker_index = 0

    try:
        worker_total = int(os.getenv("PFA_WORKER_TOTAL", "1"))
    except ValueError:
        worker_total = 1

    return worker_id, max(worker_index, 0), max(worker_total, 1)
