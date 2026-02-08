"""系统配置控制器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services import config_service

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
    context = {**base_context(request), "smtp": smtp, "saved": False}
    return templates.TemplateResponse("pages/config.html", context)


@router.post("/config", response_class=HTMLResponse)
async def config_save(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: str = Form(""),
    smtp_user: str = Form(""),
    smtp_pass: str = Form(""),
    smtp_from: str = Form(""),
    smtp_ssl: str = Form(""),
) -> HTMLResponse:
    payload = {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_pass": smtp_pass,
        "smtp_from": smtp_from,
        "smtp_ssl": smtp_ssl,
    }
    await config_service.save_smtp_config(payload)
    smtp = await config_service.get_smtp_config()
    context = {**base_context(request), "smtp": smtp, "saved": True}
    return templates.TemplateResponse("pages/config.html", context)
