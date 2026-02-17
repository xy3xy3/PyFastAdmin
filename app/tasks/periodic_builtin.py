"""内置周期任务注册。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from app.config import LOG_CLEANUP_INTERVAL_SECONDS, LOG_RETENTION_DAYS
from app.models import OperationLog
from app.services import backup_service
from app.services.queue_service import enqueue_task
from app.services.redis_service import get_redis
from app.services.task_registry import DisplayColumn, register_periodic_task

logger = logging.getLogger(__name__)

_BACKUP_LAST_RUN_KEY = "pfa:periodic:backup:last_run_ts"


async def _run_log_cleanup() -> None:
    """按保留天数清理历史操作日志。"""

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(LOG_RETENTION_DAYS, 1))
    result = await OperationLog.find(OperationLog.created_at < cutoff).delete()
    deleted_count = int(getattr(result, "deleted_count", 0))
    logger.info("操作日志清理完成，删除 %d 条", deleted_count)


async def _log_cleanup_display_values() -> dict[str, str]:
    """返回日志清理任务动态展示字段。"""

    return {
        "interval_seconds": str(LOG_CLEANUP_INTERVAL_SECONDS),
        "retention_days": str(LOG_RETENTION_DAYS),
    }


async def _run_backup_auto() -> None:
    """按备份配置执行自动备份调度。"""

    config = await backup_service.get_backup_config()
    if not bool(config.get("enabled")):
        return

    interval_hours = max(int(config.get("interval_hours") or 24), 1)
    interval_seconds = interval_hours * 3600

    redis = await get_redis()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    last_run_raw = await redis.get(_BACKUP_LAST_RUN_KEY)
    if last_run_raw:
        try:
            last_run_ts = int(str(last_run_raw))
        except (TypeError, ValueError):
            last_run_ts = 0
        if now_ts - last_run_ts < interval_seconds:
            return

    record = await backup_service.run_backup()
    if record.status != "success":
        raise RuntimeError(record.error or "自动备份执行失败")

    await redis.set(_BACKUP_LAST_RUN_KEY, str(now_ts))

    # 广播一个示例队列消息，便于开发环境验证队列消费链路。
    await enqueue_task(
        "pfa:queue:demo_events",
        {
            "event": "backup_completed",
            "record_id": str(record.id),
            "status": record.status,
        },
    )


async def _backup_display_values() -> dict[str, str]:
    """返回自动备份任务动态展示字段。"""

    config = await backup_service.get_backup_config()
    return {
        "enabled": "yes" if bool(config.get("enabled")) else "no",
        "interval_hours": str(max(int(config.get("interval_hours") or 24), 1)),
    }


def register_tasks() -> None:
    """注册内置周期任务（幂等）。"""

    try:
        register_periodic_task(
            key="operation_log_cleanup",
            name="操作日志清理",
            interval_seconds=max(LOG_CLEANUP_INTERVAL_SECONDS, 30),
            runner=_run_log_cleanup,
            tags=["system", "logs"],
            display_columns=[
                DisplayColumn(key="interval_seconds", label="执行间隔(s)"),
                DisplayColumn(key="retention_days", label="保留天数"),
            ],
            display_values_provider=_log_cleanup_display_values,
        )
    except ValueError:
        pass

    try:
        register_periodic_task(
            key="backup_auto_scheduler",
            name="自动备份调度",
            interval_seconds=60,
            runner=_run_backup_auto,
            tags=["system", "backup"],
            display_columns=[
                DisplayColumn(key="enabled", label="已启用"),
                DisplayColumn(key="interval_hours", label="备份间隔(小时)"),
            ],
            display_values_provider=_backup_display_values,
        )
    except ValueError:
        pass


register_tasks()
