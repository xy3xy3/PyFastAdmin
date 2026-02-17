from __future__ import annotations

import re

import httpx
import pytest

from app.main import app
from app.services import admin_user_service, auth_service, role_service


def _extract_login_csrf(html: str) -> str:
    """从登录页提取 CSRF Token。"""

    matched = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert matched, "登录页未返回 csrf_token"
    return matched.group(1)


async def _seed_admin(
    *,
    username: str,
    password: str,
    role_slug: str,
    permissions: list[dict[str, str]],
) -> None:
    """创建集成测试管理员账号。"""

    await role_service.create_role(
        {
            "name": f"{role_slug} 角色",
            "slug": role_slug,
            "status": "enabled",
            "description": "integration",
            "permissions": [
                {
                    "resource": item["resource"],
                    "action": item["action"],
                    "status": "enabled",
                }
                for item in permissions
            ],
        }
    )
    await admin_user_service.create_admin(
        {
            "username": username,
            "display_name": username,
            "email": "",
            "role_slug": role_slug,
            "status": "enabled",
            "password_hash": auth_service.hash_password(password),
        }
    )


async def _login(client: httpx.AsyncClient, *, username: str, password: str, next_path: str) -> None:
    """执行登录流程。"""

    page = await client.get("/admin/login")
    assert page.status_code == 200
    csrf_token = _extract_login_csrf(page.text)

    response = await client.post(
        "/admin/login",
        data={
            "username": username,
            "password": password,
            "next": next_path,
            "csrf_token": csrf_token,
        },
    )
    assert response.status_code == 302


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_task_pages_accessible_with_read_permission(initialized_db) -> None:
    """具备 read 权限时应可访问异步任务与队列消费页面。"""

    await _seed_admin(
        username="monitor_admin",
        password="monitor_pass_123",
        role_slug="monitor_role",
        permissions=[
            {"resource": "async_tasks", "action": "read"},
            {"resource": "queue_consumers", "action": "read"},
        ],
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await _login(client, username="monitor_admin", password="monitor_pass_123", next_path="/admin/async_tasks")

        async_page = await client.get("/admin/async_tasks")
        queue_page = await client.get("/admin/queue_consumers")

        assert async_page.status_code == 200
        assert queue_page.status_code == 200


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_task_pages_forbidden_without_read_permission(initialized_db) -> None:
    """缺少 read 权限时应返回 403。"""

    await _seed_admin(
        username="no_monitor_admin",
        password="monitor_pass_123",
        role_slug="no_monitor_role",
        permissions=[
            {"resource": "dashboard_home", "action": "read"},
        ],
    )

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await _login(client, username="no_monitor_admin", password="monitor_pass_123", next_path="/admin/dashboard")

        async_page = await client.get("/admin/async_tasks")
        queue_page = await client.get("/admin/queue_consumers")

        assert async_page.status_code == 403
        assert queue_page.status_code == 403
