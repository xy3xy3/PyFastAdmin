"""登录、个人资料、修改密码控制器。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services import auth_service, admin_user_service

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(prefix="/admin")


def base_context(request: Request) -> dict[str, Any]:
    return {
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str | None = None) -> HTMLResponse:
    context = {"request": request, "next": next or "/admin/rbac", "error": ""}
    return templates.TemplateResponse("pages/login.html", context)


@router.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/admin/rbac"),
) -> HTMLResponse:
    admin = await auth_service.authenticate(username.strip(), password)
    if not admin:
        context = {
            "request": request,
            "next": next,
            "error": "账号或密码不正确，或账号已被禁用。",
        }
        return templates.TemplateResponse("pages/login.html", context, status_code=401)

    request.session["admin_id"] = str(admin.id)
    request.session["admin_name"] = admin.display_name
    return RedirectResponse(url=next or "/admin/rbac", status_code=302)


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=302)


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request) -> HTMLResponse:
    admin_id = request.session.get("admin_id")
    admin = await auth_service.get_admin_by_id(admin_id)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    context = {
        **base_context(request),
        "admin": admin,
        "saved": False,
    }
    return templates.TemplateResponse("pages/profile.html", context)


@router.post("/profile", response_class=HTMLResponse)
async def profile_update(
    request: Request,
    display_name: str = Form(""),
    email: str = Form(""),
) -> HTMLResponse:
    admin_id = request.session.get("admin_id")
    admin = await auth_service.get_admin_by_id(admin_id)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    payload = {
        "display_name": display_name.strip() or admin.display_name,
        "email": email.strip(),
    }
    await admin_user_service.update_admin(admin, payload)
    request.session["admin_name"] = admin.display_name

    context = {
        **base_context(request),
        "admin": admin,
        "saved": True,
    }
    return templates.TemplateResponse("pages/profile.html", context)


@router.get("/password", response_class=HTMLResponse)
async def password_page(request: Request) -> HTMLResponse:
    admin_id = request.session.get("admin_id")
    admin = await auth_service.get_admin_by_id(admin_id)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    context = {
        **base_context(request),
        "error": "",
        "saved": False,
    }
    return templates.TemplateResponse("pages/password.html", context)


@router.post("/password", response_class=HTMLResponse)
async def password_update(
    request: Request,
    old_password: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
) -> HTMLResponse:
    admin_id = request.session.get("admin_id")
    admin = await auth_service.get_admin_by_id(admin_id)
    if not admin:
        return RedirectResponse(url="/admin/login", status_code=302)

    if len(new_password) < 6:
        context = {**base_context(request), "error": "新密码至少 6 位。", "saved": False}
        return templates.TemplateResponse("pages/password.html", context, status_code=422)

    if new_password != confirm_password:
        context = {**base_context(request), "error": "两次输入的密码不一致。", "saved": False}
        return templates.TemplateResponse("pages/password.html", context, status_code=422)

    ok = await auth_service.change_password(admin, old_password, new_password)
    if not ok:
        context = {**base_context(request), "error": "旧密码不正确。", "saved": False}
        return templates.TemplateResponse("pages/password.html", context, status_code=422)

    context = {**base_context(request), "error": "", "saved": True}
    return templates.TemplateResponse("pages/password.html", context)
