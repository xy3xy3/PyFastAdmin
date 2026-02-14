from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.apps.admin import navigation, registry
from app.main import app
from app.services import admin_user_service, auth_service, permission_service, role_service

TEMPLATES_DIR = Path("app/apps/admin/templates")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _extract_login_csrf(html: str) -> str:
    """从登录页提取隐藏表单 CSRF Token。"""

    matched = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert matched, "登录页未返回 csrf_token"
    return matched.group(1)


def _extract_page_csrf(html: str) -> str:
    """从后台页面提取 meta CSRF Token。"""

    matched = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    assert matched, "后台页面未返回 csrf-token meta"
    return matched.group(1)


async def _seed_admin(username: str, password: str, role_slug: str, display_name: str) -> None:
    """初始化可登录管理员账号。"""

    await role_service.create_role(
        {
            "name": f"{display_name}角色",
            "slug": role_slug,
            "status": "enabled",
            "description": "integration",
            "permissions": [
                {"resource": "admin_users", "action": "read", "status": "enabled"},
            ],
        }
    )
    await admin_user_service.create_admin(
        {
            "username": username,
            "display_name": display_name,
            "email": "",
            "role_slug": role_slug,
            "status": "enabled",
            "password_hash": auth_service.hash_password(password),
        }
    )


async def _login_and_get_csrf(
    client: httpx.AsyncClient,
    *,
    username: str,
    password: str,
    next_path: str,
) -> str:
    """执行登录并返回落地页面 CSRF Token。"""

    login_page = await client.get("/admin/login")
    assert login_page.status_code == 200
    login_token = _extract_login_csrf(login_page.text)

    login_response = await client.post(
        "/admin/login",
        data={
            "username": username,
            "password": password,
            "next": next_path,
            "csrf_token": login_token,
        },
    )
    assert login_response.status_code == 302

    landing = await client.get(login_response.headers.get("location") or next_path)
    assert landing.status_code == 200
    return _extract_page_csrf(landing.text)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generated_module_nav_and_breadcrumb_auto_injected(initialized_db, tmp_path, monkeypatch) -> None:
    """脚手架生成的导航配置应自动注入菜单与面包屑。"""

    module_key = "it_temp_nav"
    module_url = f"/admin/{module_key}"
    module_name = "临时模块菜单"

    registry_dir = tmp_path / "registry_generated"
    registry_dir.mkdir(parents=True, exist_ok=True)
    nav_dir = tmp_path / "nav_generated"
    nav_dir.mkdir(parents=True, exist_ok=True)

    registry_payload = {
        "group_key": "system",
        "node": {
            "key": module_key,
            "name": "临时模块",
            "url": module_url,
            "mode": "table",
            "actions": ["create", "read", "update", "delete"],
        },
    }
    (registry_dir / f"{module_key}.json").write_text(
        json.dumps(registry_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    nav_payload = {
        "group_key": "system",
        "node": {
            "resource": module_key,
            "name": module_name,
            "url": module_url,
            "icon": "fa-solid fa-puzzle-piece",
            "menu_visible": True,
            "match_prefixes": [module_url],
        },
    }
    (nav_dir / f"{module_key}.json").write_text(
        json.dumps(nav_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(registry, "REGISTRY_GENERATED_DIR", registry_dir)
    monkeypatch.setattr(navigation, "ADMIN_TREE", registry.build_admin_tree())
    monkeypatch.setattr(navigation, "NAV_GENERATED_DIR", nav_dir)
    monkeypatch.setattr(navigation, "ADMIN_NAV_TREE", navigation.build_admin_nav_tree())

    async def fake_resolve_permission_map(request: Request) -> dict[str, set[str]]:
        """注入测试权限，避免依赖角色持久化数据。"""

        request.state.current_admin_model = SimpleNamespace(id="it-admin", status="enabled")
        request.state.current_role_model = SimpleNamespace(slug="it-role", status="enabled")
        request.state.permission_flags = {
            "resources": {
                "admin_users": {"read": True},
                module_key: {"read": True},
                "profile": {"read": False},
                "password": {"read": False},
                "dashboard_home": {"read": False},
            },
            "admin_users": {"read": True},
            module_key: {"read": True},
            "profile": {"read": False},
            "password": {"read": False},
            "dashboard": {"read": False},
            "menus": {"security": True, "system": True, "profile": False},
        }
        return {
            "admin_users": {"read"},
            module_key: {"read"},
        }

    monkeypatch.setattr(permission_service, "resolve_permission_map", fake_resolve_permission_map)

    template_name = f"{module_key}_it_page.html"
    template_path = TEMPLATES_DIR / "pages" / template_name
    template_path.write_text(
        """{% extends \"base.html\" %}\n{% block content %}<div>IT NAV PAGE</div>{% endblock %}\n""",
        encoding="utf-8",
    )

    router = APIRouter(prefix="/admin")

    @router.get(
        f"/{module_key}",
        response_class=HTMLResponse,
        openapi_extra={"permission": {"resource": "admin_users", "action": "read"}},
    )
    async def temp_module_page(request: Request) -> HTMLResponse:
        """临时模块页面，仅用于导航注入集成测试。"""

        return templates.TemplateResponse(
            f"pages/{template_name}",
            {
                "request": request,
                "current_admin": request.session.get("admin_name"),
            },
        )

    base_route_count = len(app.router.routes)
    app.include_router(router)
    permission_service._build_permission_rules.cache_clear()

    await _seed_admin(
        username="it_nav_admin",
        password="it_nav_pass_123",
        role_slug="it_nav_role",
        display_name="导航测试管理员",
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False) as client:
            page_csrf = await _login_and_get_csrf(
                client,
                username="it_nav_admin",
                password="it_nav_pass_123",
                next_path=module_url,
            )
            assert page_csrf

            response = await client.get(module_url)
            assert response.status_code == 200
            assert f'href="{module_url}"' in response.text
            assert module_name in response.text
            assert '<span class="breadcrumb-muted">系统工具</span>' in response.text
            assert f'<span class="breadcrumb-current">{module_name}</span>' in response.text
    finally:
        if template_path.exists():
            template_path.unlink()
        del app.router.routes[base_route_count:]
        permission_service._build_permission_rules.cache_clear()
