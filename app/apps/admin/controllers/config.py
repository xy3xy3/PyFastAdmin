"""系统配置控制器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services import config_service, log_service, permission_decorator

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(prefix="/admin")


def base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    smtp = await config_service.get_smtp_config()
    audit_actions = await config_service.get_audit_log_actions()
    context = {
        **base_context(request),
        "smtp": smtp,
        "saved": False,
        "audit_actions": audit_actions,
        "audit_action_labels": config_service.AUDIT_ACTION_LABELS,
    }
    await log_service.record_request(
        request,
        action="read",
        module="config",
        target="系统配置",
        detail="访问系统配置页面",
    )
    return templates.TemplateResponse("pages/config.html", context)


@router.post("/config", response_class=HTMLResponse)
@permission_decorator.permission_meta("config", "update")
async def config_save(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: str = Form(""),
    smtp_user: str = Form(""),
    smtp_pass: str = Form(""),
    smtp_from: str = Form(""),
    smtp_ssl: str = Form(""),
) -> HTMLResponse:
    form_data = await request.form()
    payload = {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
        "smtp_from": smtp_from,
        "smtp_ssl": smtp_ssl,
    }
    selected_actions = [
        str(value)
        for value in form_data.getlist("audit_actions")
        if isinstance(value, str)
    ]

    await config_service.save_smtp_config(payload)
    audit_actions = await config_service.save_audit_log_actions(selected_actions)
    smtp = await config_service.get_smtp_config()
    context = {
        **base_context(request),
        "smtp": smtp,
        "saved": True,
        "audit_actions": audit_actions,
        "audit_action_labels": config_service.AUDIT_ACTION_LABELS,
    }
    detail = (
        "更新系统配置，日志类型："
        + ("、".join(config_service.AUDIT_ACTION_LABELS.get(item, item) for item in audit_actions) if audit_actions else "不记录")
    )
    await log_service.record_request(
        request,
        action="update",
        module="config",
        target="系统配置",
        detail=detail,
    )
    return templates.TemplateResponse("pages/config.html", context)
