"""管理员鉴权中间件。"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


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

        return await call_next(request)
