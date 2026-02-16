from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.sessions import SessionMiddleware

from app.apps.admin.controllers.auth import router as auth_router
from app.services import admin_user_service, auth_service, csrf_service, log_service


@dataclass
class FakeAdmin:
    """测试用管理员对象。"""

    id: str
    username: str
    display_name: str
    email: str
    role_slug: str
    status: str


@dataclass
class AuthTestState:
    """auth 控制器测试状态。"""

    admin: FakeAdmin
    authenticate_result: FakeAdmin | None
    change_password_ok: bool


@pytest.fixture
def auth_test_state(monkeypatch: pytest.MonkeyPatch) -> AuthTestState:
    """构建 auth 控制器测试依赖并打桩。"""

    state = AuthTestState(
        admin=FakeAdmin(
            id="unit-admin-id",
            username="unit_admin",
            display_name="单测管理员",
            email="unit_admin@example.com",
            role_slug="admin",
            status="enabled",
        ),
        authenticate_result=None,
        change_password_ok=True,
    )

    async def fake_authenticate(_username: str, _password: str) -> FakeAdmin | None:
        return state.authenticate_result

    async def fake_get_admin_by_id(admin_id: str | None) -> FakeAdmin | None:
        if str(admin_id or "") == state.admin.id:
            return state.admin
        return None

    async def fake_update_admin(admin: FakeAdmin, payload: dict[str, str]) -> FakeAdmin:
        admin.display_name = payload["display_name"]
        admin.email = payload["email"]
        return admin

    async def fake_change_password(_admin: FakeAdmin, _old_password: str, _new_password: str) -> bool:
        return state.change_password_ok

    async def fake_record_request(*_args, **_kwargs) -> bool:
        return True

    async def fake_record_action(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(auth_service, "authenticate", fake_authenticate)
    monkeypatch.setattr(auth_service, "get_admin_by_id", fake_get_admin_by_id)
    monkeypatch.setattr(auth_service, "change_password", fake_change_password)
    monkeypatch.setattr(admin_user_service, "update_admin", fake_update_admin)
    monkeypatch.setattr(log_service, "record_request", fake_record_request)
    monkeypatch.setattr(log_service, "record_action", fake_record_action)
    monkeypatch.setattr(csrf_service, "rotate_csrf_token", lambda _session: "csrf-unit-token")

    return state


@pytest.fixture
def auth_test_app(auth_test_state: AuthTestState) -> FastAPI:
    """构建仅用于 auth 控制器响应断言的测试应用。"""

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="unit-test-secret")

    @app.middleware("http")
    async def inject_request_state(request: Request, call_next):
        """注入模板渲染依赖的 request.state 字段。"""

        request.scope.setdefault("session", {})
        request.state.permission_flags = {
            "profile": {"read": True, "update_self": True},
            "password": {"read": True, "update_self": True},
        }
        session_data = request.scope.get("session", {})
        csrf_token = session_data.get("csrf_token", "") if isinstance(session_data, dict) else ""
        request.state.csrf_token = csrf_token
        return await call_next(request)

    @app.get("/_test/login-session")
    async def _test_login_session(request: Request) -> PlainTextResponse:
        """写入登录态 session，供 profile/password 路由使用。"""

        request.session["admin_id"] = auth_test_state.admin.id
        request.session["admin_name"] = auth_test_state.admin.display_name
        request.session["csrf_token"] = "csrf-unit-token"
        return PlainTextResponse("ok")

    app.include_router(auth_router)
    return app


@pytest.fixture
async def auth_client(auth_test_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """提供基于 ASGITransport 的异步测试客户端。"""

    transport = httpx.ASGITransport(app=auth_test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=False) as client:
        yield client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401_and_error_html(
    auth_client: httpx.AsyncClient,
    auth_test_state: AuthTestState,
) -> None:
    """登录失败时应返回 401，并在模板中回显错误信息。"""

    auth_test_state.authenticate_result = None

    response = await auth_client.post(
        "/admin/login",
        data={
            "username": "bad-user",
            "password": "bad-pass",
            "next": "/admin/dashboard",
        },
    )

    assert response.status_code == 401
    assert "账号或密码不正确，或账号已被禁用。" in response.text
    assert "管理员登录" in response.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_profile_invalid_email_returns_422_and_error_html(
    auth_client: httpx.AsyncClient,
    auth_test_state: AuthTestState,
) -> None:
    """个人资料提交非法邮箱时应返回 422，并在页面回显校验错误。"""

    auth_test_state.authenticate_result = auth_test_state.admin
    await auth_client.get("/_test/login-session")

    response = await auth_client.post(
        "/admin/profile",
        data={
            "display_name": "新的显示名",
            "email": "not-an-email",
        },
    )

    assert response.status_code == 422
    assert "邮箱格式不合法" in response.text
    assert "个人资料" in response.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_password_wrong_old_password_returns_422_and_error_html(
    auth_client: httpx.AsyncClient,
    auth_test_state: AuthTestState,
) -> None:
    """旧密码错误时应返回 422，并在页面回显失败原因。"""

    auth_test_state.authenticate_result = auth_test_state.admin
    auth_test_state.change_password_ok = False
    await auth_client.get("/_test/login-session")

    response = await auth_client.post(
        "/admin/password",
        data={
            "old_password": "wrong-old",
            "new_password": "valid-new-pass",
            "confirm_password": "valid-new-pass",
        },
    )

    assert response.status_code == 422
    assert "旧密码不正确。" in response.text
    assert "修改密码" in response.text
