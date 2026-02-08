"""管理员管理控制器。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from beanie import PydanticObjectId
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services import admin_user_service, auth_service

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(prefix="/admin")


def fmt_dt(value: datetime | None) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        return value.strftime("%Y-%m-%d %H:%M")
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


templates.env.filters["fmt_dt"] = fmt_dt

STATUS_META: dict[str, dict[str, str]] = {
    "enabled": {"label": "启用", "color": "#2f855a"},
    "disabled": {"label": "禁用", "color": "#b7791f"},
}

ROLE_META = {
    "super": "超级管理员",
    "admin": "管理员",
    "viewer": "只读",
}


def base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


def build_form_data(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "username": values.get("username", ""),
        "display_name": values.get("display_name", ""),
        "email": values.get("email", ""),
        "role": values.get("role", "admin"),
        "status": values.get("status", "enabled"),
        "password": values.get("password", ""),
    }


def form_errors(values: dict[str, Any], is_create: bool) -> list[str]:
    errors: list[str] = []
    if len(values.get("username", "")) < 3:
        errors.append("账号至少 3 个字符")
    if len(values.get("display_name", "")) < 2:
        errors.append("显示名称至少 2 个字符")
    if values.get("status") not in STATUS_META:
        errors.append("状态不合法")
    if values.get("role") not in ROLE_META:
        errors.append("角色不合法")
    if is_create and len(values.get("password", "")) < 6:
        errors.append("初始密码至少 6 位")
    return errors


@router.get("/users", response_class=HTMLResponse)
async def admin_users_page(request: Request) -> HTMLResponse:
    items = await admin_user_service.list_admins()
    stats = {
        "total": len(items),
        "enabled": sum(1 for item in items if item.status == "enabled"),
        "disabled": sum(1 for item in items if item.status == "disabled"),
        "latest": fmt_dt(items[0].updated_at) if items else None,
    }
    context = {
        **base_context(request),
        "items": items,
        "stats": stats,
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    return templates.TemplateResponse("pages/admin_users.html", context)


@router.get("/users/table", response_class=HTMLResponse)
async def admin_users_table(request: Request, q: str | None = None) -> HTMLResponse:
    items = await admin_user_service.list_admins(q)
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    return templates.TemplateResponse("partials/admin_users_table.html", context)


@router.get("/users/new", response_class=HTMLResponse)
async def admin_users_new(request: Request) -> HTMLResponse:
    form = build_form_data({})
    context = {
        **base_context(request),
        "mode": "create",
        "action": "/admin/users",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    return templates.TemplateResponse("partials/admin_users_form.html", context)


@router.get("/users/{item_id}/edit", response_class=HTMLResponse)
async def admin_users_edit(request: Request, item_id: PydanticObjectId) -> HTMLResponse:
    item = await admin_user_service.get_admin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="账号不存在")

    form = build_form_data(
        {
            "username": item.username,
            "display_name": item.display_name,
            "email": item.email,
            "role": item.role,
            "status": item.status,
            "password": "",
        }
    )
    context = {
        **base_context(request),
        "mode": "edit",
        "action": f"/admin/users/{item_id}",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    return templates.TemplateResponse("partials/admin_users_form.html", context)


@router.post("/users", response_class=HTMLResponse)
async def admin_users_create(
    request: Request,
    username: str = Form(""),
    display_name: str = Form(""),
    email: str = Form(""),
    role: str = Form("admin"),
    status: str = Form("enabled"),
    password: str = Form(""),
) -> HTMLResponse:
    form = build_form_data(
        {
            "username": username.strip(),
            "display_name": display_name.strip(),
            "email": email.strip(),
            "role": role,
            "status": status,
            "password": password,
        }
    )

    errors = form_errors(form, is_create=True)
    if await admin_user_service.get_admin_by_username(form["username"]):
        errors.append("账号已存在")

    if errors:
        context = {
            **base_context(request),
            "mode": "create",
            "action": "/admin/users",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "role_meta": ROLE_META,
        }
        return templates.TemplateResponse(
            "partials/admin_users_form.html", context, status_code=422
        )

    payload = {
        "username": form["username"],
        "display_name": form["display_name"],
        "email": form["email"],
        "role": form["role"],
        "status": form["status"],
        "password_hash": auth_service.hash_password(form["password"]),
    }
    await admin_user_service.create_admin(payload)

    items = await admin_user_service.list_admins()
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    response = templates.TemplateResponse("partials/admin_users_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"admin-toast": {"title": "已创建", "message": "管理员账号已保存"}, "rbac-close": true}'
    )
    return response


@router.post("/users/{item_id}", response_class=HTMLResponse)
async def admin_users_update(
    request: Request,
    item_id: PydanticObjectId,
    display_name: str = Form(""),
    email: str = Form(""),
    role: str = Form("admin"),
    status: str = Form("enabled"),
    password: str = Form(""),
) -> HTMLResponse:
    item = await admin_user_service.get_admin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="账号不存在")

    form = build_form_data(
        {
            "username": item.username,
            "display_name": display_name.strip(),
            "email": email.strip(),
            "role": role,
            "status": status,
            "password": password,
        }
    )

    errors = form_errors(form, is_create=False)
    if errors:
        context = {
            **base_context(request),
            "mode": "edit",
            "action": f"/admin/users/{item_id}",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "role_meta": ROLE_META,
        }
        return templates.TemplateResponse(
            "partials/admin_users_form.html", context, status_code=422
        )

    payload = {
        "display_name": form["display_name"],
        "email": form["email"],
        "role": form["role"],
        "status": form["status"],
        "password_hash": auth_service.hash_password(form["password"]) if form["password"] else "",
    }
    await admin_user_service.update_admin(item, payload)
    if str(item.id) == str(request.session.get("admin_id")):
        request.session["admin_name"] = item.display_name

    items = await admin_user_service.list_admins()
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    response = templates.TemplateResponse("partials/admin_users_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"admin-toast": {"title": "已更新", "message": "管理员账号已修改"}, "rbac-close": true}'
    )
    return response


@router.delete("/users/{item_id}", response_class=HTMLResponse)
async def admin_users_delete(request: Request, item_id: PydanticObjectId) -> HTMLResponse:
    item = await admin_user_service.get_admin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="账号不存在")

    if str(item.id) == str(request.session.get("admin_id")):
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    await admin_user_service.delete_admin(item)
    items = await admin_user_service.list_admins()
    context = {
        **base_context(request),
        "items": items,
        "status_meta": STATUS_META,
        "role_meta": ROLE_META,
    }
    response = templates.TemplateResponse("partials/admin_users_table.html", context)
    response.headers["HX-Trigger"] = (
        '{"admin-toast": {"title": "已删除", "message": "管理员账号已移除"}}'
    )
    return response
