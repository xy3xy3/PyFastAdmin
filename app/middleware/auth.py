"""管理员鉴权中间件。"""

from __future__ import annotations

from html import escape

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from app.services import permission_service


def forbidden_response(request: Request, message: str) -> Response:
    """返回统一的 403 响应。"""

    if request.headers.get("HX-Request") == "true":
        return HTMLResponse(content=message, status_code=403)

    content = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8' />"
        "<meta name='viewport' content='width=device-width, initial-scale=1' />"
        "<title>403 无权限</title></head><body style='font-family: sans-serif; padding: 2rem;'>"
        "<h1 style='margin: 0 0 0.75rem;'>403 无权限</h1>"
        f"<p style='margin: 0;'>{escape(message)}</p>"
        "</body></html>"
    )
    return HTMLResponse(content=content, status_code=403)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """简单的 Session 鉴权中间件。"""

    def __init__(self, app, exempt_paths: set[str] | None = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or set()

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path.startswith("/static"):
            return await call_next(request)

        if path in self.exempt_paths or path.startswith("/admin/login"):
            return await call_next(request)

        if path.startswith("/admin"):
            if not request.session.get("admin_id"):
                next_url = request.url.path
                return RedirectResponse(url=f"/admin/login?next={next_url}", status_code=302)

            permission_map = await permission_service.resolve_permission_map(request)
            if not request.state.current_admin_model:
                request.session.clear()
                next_url = request.url.path
                return RedirectResponse(url=f"/admin/login?next={next_url}", status_code=302)

            needed = permission_service.required_permission(path, request.method)
            if needed is None:
                return forbidden_response(request, "当前请求未注册权限映射，已被系统拒绝访问。")

            if not permission_service.can(permission_map, needed[0], needed[1]):
                return forbidden_response(request, "当前账号没有执行该操作的权限。")

        return await call_next(request)
