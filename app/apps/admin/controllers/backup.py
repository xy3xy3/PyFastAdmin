"""数据备份控制器。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.apps.admin.rendering import (
    base_context,
    build_pagination,
    jinja,
    parse_positive_int,
    read_request_values,
)
from app.services import backup_service, log_service, permission_decorator

router = APIRouter(prefix="/admin")

BACKUP_PAGE_SIZE = 10

# 云端供应商选项
CLOUD_PROVIDER_LABELS: dict[str, str] = {
    "aliyun_oss": "阿里云 OSS",
    "tencent_cos": "腾讯云 COS",
}


async def build_table_context(
    request: Request,
    page: int,
    page_size: int,
    action_feedback: dict[str, str] | None = None,
) -> dict[str, Any]:
    """构建备份记录表格上下文。"""

    records, total = await backup_service.list_backup_records(page=page, page_size=page_size)
    pagination = build_pagination(total, page, page_size)

    return {
        **base_context(request),
        "records": records,
        "pagination": pagination,
        "action_feedback": action_feedback,
    }


@router.get("/backup")
@permission_decorator.permission_meta("backup_records", "read")
@jinja.page("pages/backup.html")
async def backup_page(request: Request) -> dict[str, Any]:
    """备份管理主页。"""

    config = await backup_service.get_backup_config()
    collections = await backup_service.get_collection_names()

    context = await build_table_context(request, page=1, page_size=BACKUP_PAGE_SIZE)
    context.update(
        {
            "config": config,
            "saved": False,
            "collections": collections,
            "cloud_provider_labels": CLOUD_PROVIDER_LABELS,
        }
    )

    await log_service.record_request(
        request,
        action="read",
        module="backup",
        target="数据备份",
        detail="访问数据备份页面",
    )
    return context


@router.get("/backup/table")
@permission_decorator.permission_meta("backup_records", "read")
@jinja.page("partials/backup_table.html")
async def backup_table(request: Request) -> dict[str, Any]:
    """HTMX 局部刷新备份记录表格。"""

    page = parse_positive_int(request.query_params.get("page"), default=1)
    page_size = parse_positive_int(request.query_params.get("page_size"), default=BACKUP_PAGE_SIZE)
    return await build_table_context(request, page=page, page_size=page_size)


@router.get("/backup/collections")
@permission_decorator.permission_meta("backup_config", "read")
@jinja.page("partials/backup_collections.html")
async def backup_collections(request: Request) -> dict[str, Any]:
    """HTMX 局部刷新可选集合列表。"""

    config = await backup_service.get_backup_config()
    collections = await backup_service.get_collection_names()
    return {
        **base_context(request),
        "collections": collections,
        "excluded_collections": set(config.get("excluded_collections", [])),
    }


@router.post("/backup")
@permission_decorator.permission_meta("backup_config", "update")
@jinja.page("pages/backup.html")
async def backup_save_config(request: Request) -> dict[str, Any]:
    """保存备份配置。"""

    form = await request.form()

    payload: dict[str, Any] = {
        "enabled": form.get("enabled") == "on",
        "local_dir": str(form.get("local_dir", "backups")).strip(),
        "local_retention": form.get("local_retention", "5"),
        "interval_hours": form.get("interval_hours", "24"),
        "excluded_collections": [
            str(value)
            for value in form.getlist("excluded_collections")
            if isinstance(value, str) and value.strip()
        ],
        "cloud_enabled": form.get("cloud_enabled") == "on",
        "cloud_providers": [
            str(value)
            for value in form.getlist("cloud_providers")
            if isinstance(value, str) and value.strip()
        ],
        "cloud_path": str(form.get("cloud_path", "backups/pyfastadmin")).strip(),
        "cloud_retention": form.get("cloud_retention", "10"),
        # OSS
        "oss_region": str(form.get("oss_region", "")).strip(),
        "oss_endpoint": str(form.get("oss_endpoint", "")).strip(),
        "oss_access_key_id": str(form.get("oss_access_key_id", "")).strip(),
        "oss_access_key_secret": str(form.get("oss_access_key_secret", "")).strip(),
        "oss_bucket": str(form.get("oss_bucket", "")).strip(),
        # COS
        "cos_region": str(form.get("cos_region", "")).strip(),
        "cos_secret_id": str(form.get("cos_secret_id", "")).strip(),
        "cos_secret_key": str(form.get("cos_secret_key", "")).strip(),
        "cos_bucket": str(form.get("cos_bucket", "")).strip(),
    }

    config = await backup_service.save_backup_config(payload)
    collections = await backup_service.get_collection_names()
    context = await build_table_context(request, page=1, page_size=BACKUP_PAGE_SIZE)
    context.update(
        {
            "config": config,
            "saved": True,
            "collections": collections,
            "cloud_provider_labels": CLOUD_PROVIDER_LABELS,
        }
    )

    await log_service.record_request(
        request,
        action="update",
        module="backup",
        target="备份配置",
        detail="更新数据备份配置",
    )
    return context


@router.post("/backup/trigger")
@permission_decorator.permission_meta("backup_records", "trigger")
@jinja.page("partials/backup_table.html")
async def backup_trigger(request: Request) -> dict[str, Any]:
    """手动触发一次备份。"""

    values = await read_request_values(request)
    page = parse_positive_int(values.get("page"), default=1)
    page_size = parse_positive_int(values.get("page_size"), default=BACKUP_PAGE_SIZE)

    record = await backup_service.run_backup()
    feedback = {
        "variant": "success" if record.status == "success" else "error",
        "message": "手动备份执行完成" if record.status == "success" else f"手动备份失败：{record.error or '未知错误'}",
    }
    context = await build_table_context(
        request,
        page=page,
        page_size=page_size,
        action_feedback=feedback,
    )

    await log_service.record_request(
        request,
        action="trigger",
        module="backup",
        target="手动备份",
        detail=f"手动触发数据库备份，状态：{record.status}",
    )
    return context


@router.post("/backup/{record_id}/restore")
@permission_decorator.permission_meta("backup_records", "restore")
@jinja.page("partials/backup_table.html")
async def backup_restore(request: Request, record_id: str) -> dict[str, Any]:
    """按指定备份记录恢复数据库。"""

    values = await read_request_values(request)
    page = parse_positive_int(values.get("page"), default=1)
    page_size = parse_positive_int(values.get("page_size"), default=BACKUP_PAGE_SIZE)

    success, message = await backup_service.restore_backup_record(record_id)
    feedback = {
        "variant": "success" if success else "error",
        "message": message,
    }
    context = await build_table_context(
        request,
        page=page,
        page_size=page_size,
        action_feedback=feedback,
    )

    await log_service.record_request(
        request,
        action="restore",
        module="backup",
        target="恢复备份",
        target_id=record_id,
        detail=f"恢复备份记录 {record_id}：{message}",
    )
    return context


@router.delete("/backup/{record_id}")
@permission_decorator.permission_meta("backup_records", "delete")
@jinja.page("partials/backup_table.html")
async def backup_delete(request: Request, record_id: str) -> dict[str, Any]:
    """删除一条备份记录。"""

    values = await read_request_values(request)
    page = parse_positive_int(values.get("page"), default=1)
    page_size = parse_positive_int(values.get("page_size"), default=BACKUP_PAGE_SIZE)

    deleted = await backup_service.delete_backup_record(record_id)
    feedback = {
        "variant": "success" if deleted else "error",
        "message": "删除备份记录成功" if deleted else "删除备份记录失败：记录不存在",
    }
    context = await build_table_context(
        request,
        page=page,
        page_size=page_size,
        action_feedback=feedback,
    )

    await log_service.record_request(
        request,
        action="delete",
        module="backup",
        target="备份记录",
        target_id=record_id,
        detail=feedback["message"],
    )
    return context
