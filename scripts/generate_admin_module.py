"""后台模块脚手架命令。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

MODULE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS_DIR = ROOT / "app/apps/admin/controllers"
SERVICES_DIR = ROOT / "app/services"
PAGES_DIR = ROOT / "app/apps/admin/templates/pages"
PARTIALS_DIR = ROOT / "app/apps/admin/templates/partials"
TESTS_DIR = ROOT / "tests/unit"
REGISTRY_DIR = ROOT / "app/apps/admin/registry_generated"


def parse_args() -> argparse.Namespace:
    """解析命令参数。"""

    parser = argparse.ArgumentParser(description="生成后台 CRUD 模块骨架")
    parser.add_argument("module", help="模块标识（小写字母/数字/下划线）")
    parser.add_argument("--name", default="", help="模块中文名，默认使用 module")
    parser.add_argument("--group", default="system", help="注册分组 key，默认 system")
    parser.add_argument("--url", default="", help="资源 URL，默认 /admin/<module>")
    parser.add_argument("--force", action="store_true", help="覆盖已有文件")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将要生成的文件")
    return parser.parse_args()


def ensure_module_name(module: str) -> str:
    """校验模块名，避免生成非法路由与文件名。"""

    value = module.strip().lower()
    if not MODULE_PATTERN.fullmatch(value):
        raise ValueError("module 必须匹配 ^[a-z][a-z0-9_]{1,31}$")
    return value


def write_file(path: Path, content: str, *, force: bool, dry_run: bool) -> None:
    """写入文件，支持覆盖与 dry-run。"""

    if path.exists() and not force:
        raise FileExistsError(f"文件已存在：{path}")
    if dry_run:
        print(f"[dry-run] {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[ok] {path}")


def render_controller(module: str, title: str) -> str:
    """渲染控制器模板。"""

    return f'''"""{title} 控制器。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services import {module}_service, log_service, permission_decorator

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = BASE_DIR / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter(prefix="/admin")


def base_context(request: Request) -> dict[str, Any]:
    """构建模板基础上下文。"""

    return {{
        "request": request,
        "current_admin": request.session.get("admin_name"),
    }}


@router.get("/{module}", response_class=HTMLResponse)
async def {module}_page(request: Request) -> HTMLResponse:
    """模块列表页。"""

    items = await {module}_service.list_items()
    await log_service.record_request(
        request,
        action="read",
        module="{module}",
        target="{title}",
        detail="访问模块列表页面",
    )
    return templates.TemplateResponse("pages/{module}.html", {{**base_context(request), "items": items}})


@router.get("/{module}/table", response_class=HTMLResponse)
async def {module}_table(request: Request) -> HTMLResponse:
    """模块表格 partial。"""

    items = await {module}_service.list_items()
    return templates.TemplateResponse("partials/{module}_table.html", {{**base_context(request), "items": items}})


@router.get("/{module}/new", response_class=HTMLResponse)
async def {module}_new(request: Request) -> HTMLResponse:
    """新建弹窗。"""

    return templates.TemplateResponse(
        "partials/{module}_form.html",
        {{**base_context(request), "mode": "create", "action": "/admin/{module}", "errors": [], "form": {{}}}},
    )


@router.post("/{module}", response_class=HTMLResponse)
@permission_decorator.permission_meta("{module}", "create")
async def {module}_create(request: Request) -> HTMLResponse:
    """创建数据（脚手架模板，需按业务补充校验）。"""

    form_data = await request.form()
    payload = dict(form_data)
    created = await {module}_service.create_item(payload)
    await log_service.record_request(
        request,
        action="create",
        module="{module}",
        target="{title}",
        target_id=str(getattr(created, "id", "")),
        detail="创建记录",
    )

    items = await {module}_service.list_items()
    response = templates.TemplateResponse("partials/{module}_table.html", {{**base_context(request), "items": items}})
    response.headers["HX-Trigger"] = json.dumps(
        {{"rbac-toast": {{"title": "已创建", "message": "记录创建成功", "variant": "success"}}, "rbac-close": True}},
        ensure_ascii=True,
    )
    return response


@router.get("/{module}/{{item_id}}/edit", response_class=HTMLResponse)
async def {module}_edit(request: Request, item_id: str) -> HTMLResponse:
    """编辑弹窗。"""

    item = await {module}_service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    return templates.TemplateResponse(
        "partials/{module}_form.html",
        {{
            **base_context(request),
            "mode": "edit",
            "action": f"/admin/{module}/{{item_id}}",
            "errors": [],
            "form": item,
        }},
    )


@router.post("/{module}/{{item_id}}", response_class=HTMLResponse)
@permission_decorator.permission_meta("{module}", "update")
async def {module}_update(request: Request, item_id: str) -> HTMLResponse:
    """更新数据（脚手架模板，需按业务补充校验）。"""

    item = await {module}_service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    form_data = await request.form()
    payload = dict(form_data)
    await {module}_service.update_item(item, payload)
    await log_service.record_request(
        request,
        action="update",
        module="{module}",
        target="{title}",
        target_id=item_id,
        detail="更新记录",
    )

    items = await {module}_service.list_items()
    response = templates.TemplateResponse("partials/{module}_table.html", {{**base_context(request), "items": items}})
    response.headers["HX-Trigger"] = json.dumps(
        {{"rbac-toast": {{"title": "已更新", "message": "记录更新成功", "variant": "success"}}, "rbac-close": True}},
        ensure_ascii=True,
    )
    return response


@router.delete("/{module}/{{item_id}}", response_class=HTMLResponse)
@permission_decorator.permission_meta("{module}", "delete")
async def {module}_delete(request: Request, item_id: str) -> HTMLResponse:
    """删除数据。"""

    item = await {module}_service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")

    await {module}_service.delete_item(item)
    await log_service.record_request(
        request,
        action="delete",
        module="{module}",
        target="{title}",
        target_id=item_id,
        detail="删除记录",
    )

    items = await {module}_service.list_items()
    response = templates.TemplateResponse("partials/{module}_table.html", {{**base_context(request), "items": items}})
    response.headers["HX-Trigger"] = json.dumps(
        {{"rbac-toast": {{"title": "已删除", "message": "记录已删除", "variant": "warning"}}}},
        ensure_ascii=True,
    )
    return response
'''


def render_service(module: str) -> str:
    """渲染服务模板。"""

    return f'''"""{module} 服务层（脚手架模板）。"""

from __future__ import annotations

from typing import Any


async def list_items() -> list[dict[str, Any]]:
    """查询列表（待业务实现）。"""

    return []


async def get_item(item_id: str) -> dict[str, Any] | None:
    """按 ID 查询单条记录（待业务实现）。"""

    _ = item_id
    return None


async def create_item(payload: dict[str, Any]) -> dict[str, Any]:
    """创建记录（待业务实现）。"""

    return payload


async def update_item(item: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """更新记录（待业务实现）。"""

    item.update(payload)
    return item


async def delete_item(item: dict[str, Any]) -> None:
    """删除记录（待业务实现）。"""

    _ = item
'''


def render_page(module: str, title: str) -> str:
    """渲染页面模板。"""

    return f'''{{% extends "base.html" %}}

{{% block content %}}
<div class="space-y-4">
  <section class="card p-5">
    <div class="flex items-center justify-between gap-3">
      <h1 class="text-lg font-semibold text-slate-900">{title}</h1>
      <p class="text-sm text-slate-500">脚手架已生成，请按业务补充筛选与统计。</p>
    </div>
  </section>

  <section>
    {{% include "partials/{module}_table.html" %}}
  </section>
</div>
{{% endblock %}}
'''


def render_table(module: str, title: str) -> str:
    """渲染表格 partial 模板。"""

    return f'''<div id="{module}-table" class="card p-5">
  {{% set perm = request.state.permission_flags.resources.get("{module}", {{"create": False, "read": False, "update": False, "delete": False}}) %}}
  {{% set show_action_col = perm['update'] or perm['delete'] %}}
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h2 class="text-lg font-semibold text-slate-900">{title}列表</h2>
      <p class="mt-1 text-sm text-slate-500">共 {{{{ items | length }}}} 条记录</p>
    </div>

    {{% if perm['create'] %}}
      <button
        class="btn-primary"
        hx-get="/admin/{module}/new"
        hx-target="#modal-body"
        hx-swap="innerHTML"
        hx-indicator="#global-indicator"
        x-on:click="modalOpen = true"
      >
        新建
      </button>
    {{% endif %}}
  </div>

  <div class="mt-4 overflow-x-auto rounded-lg border border-slate-200">
    <table class="w-full min-w-[720px] text-left text-sm">
      <thead class="bg-slate-50 text-slate-600">
        <tr>
          <th class="px-4 py-3 font-medium">ID</th>
          <th class="px-4 py-3 font-medium">名称</th>
          {{% if show_action_col %}}<th class="px-4 py-3 text-right font-medium">操作</th>{{% endif %}}
        </tr>
      </thead>
      <tbody>
        {{% for item in items %}}
          <tr class="border-t border-slate-100">
            <td class="px-4 py-3 text-slate-500">{{{{ item.id if item.id is defined else '-' }}}}</td>
            <td class="px-4 py-3 text-slate-900">{{{{ item.name if item.name is defined else '-' }}}}</td>
            {{% if show_action_col %}}
              <td class="px-4 py-3 text-right">
                {{% if perm['update'] %}}
                  <button
                    class="btn-link"
                    hx-get="/admin/{module}/{{{{ item.id }}}}/edit"
                    hx-target="#modal-body"
                    hx-swap="innerHTML"
                    hx-indicator="#global-indicator"
                    x-on:click="modalOpen = true"
                  >
                    编辑
                  </button>
                {{% endif %}}
                {{% if perm['delete'] %}}
                  <button
                    class="btn-link {{% if perm['update'] %}}ml-3 {{% endif %}}text-red-500 hover:text-red-600"
                    hx-delete="/admin/{module}/{{{{ item.id }}}}"
                    hx-target="#{module}-table"
                    hx-swap="outerHTML"
                    hx-confirm="确认删除该记录吗？"
                    hx-indicator="#global-indicator"
                  >
                    删除
                  </button>
                {{% endif %}}
              </td>
            {{% endif %}}
          </tr>
        {{% else %}}
          <tr>
            <td class="px-4 py-8 text-center text-sm text-slate-500" colspan="3">暂无数据，请先创建记录。</td>
          </tr>
        {{% endfor %}}
      </tbody>
    </table>
  </div>
</div>
'''


def render_form_partial(module: str, title: str) -> str:
    """渲染表单 partial 模板。"""

    return f'''<div class="space-y-4">
  <div class="flex items-start justify-between gap-4">
    <div>
      <h2 class="font-display text-2xl text-ink">{{% if mode == "edit" %}}编辑{title}{{% else %}}新建{title}{{% endif %}}</h2>
      <p class="text-sm text-muted">脚手架模板：请补充表单字段与业务校验。</p>
    </div>
    <button class="btn-ghost px-3" x-on:click="modalOpen = false">关闭</button>
  </div>

  {{% if errors %}}
    <div class="rounded-2xl border border-black/10 bg-white/70 p-3 text-sm text-red-600">
      <p class="font-semibold">请修正以下问题：</p>
      <ul class="mt-2 list-disc pl-5">
        {{% for err in errors %}}
          <li>{{{{ err }}}}</li>
        {{% endfor %}}
      </ul>
    </div>
  {{% endif %}}

  <form class="grid gap-4" hx-post="{{{{ action }}}}" hx-target="#{module}-table" hx-swap="outerHTML" hx-indicator="#modal-indicator">
    <input type="hidden" name="csrf_token" value="{{{{ request.state.csrf_token or '' }}}}" />

    <div>
      <label class="label">名称</label>
      <input name="name" class="input" value="{{{{ form.name if form.name is defined else '' }}}}" />
    </div>

    <div class="flex flex-wrap items-center justify-end gap-3 pt-2">
      <button type="button" class="btn-ghost" x-on:click="modalOpen = false">取消</button>
      <button type="submit" class="btn-primary">保存</button>
    </div>
  </form>
</div>
'''


def render_test(module: str) -> str:
    """渲染脚手架测试模板。"""

    return f'''from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.unit
def test_{module}_registry_generated_contains_crud_actions() -> None:
    payload = json.loads(Path("app/apps/admin/registry_generated/{module}.json").read_text(encoding="utf-8"))

    assert payload["node"]["key"] == "{module}"
    assert payload["node"]["actions"] == ["create", "read", "update", "delete"]
'''


def render_registry(module: str, title: str, group: str, url: str) -> str:
    """渲染注册节点 JSON。"""

    payload = {
        "group_key": group,
        "node": {
            "key": module,
            "name": title,
            "url": url,
            "actions": ["create", "read", "update", "delete"],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    """脚手架主流程。"""

    args = parse_args()
    module = ensure_module_name(args.module)
    title = (args.name or module).strip()
    group = (args.group or "system").strip() or "system"
    url = (args.url or f"/admin/{module}").strip() or f"/admin/{module}"

    files = {
        CONTROLLERS_DIR / f"{module}.py": render_controller(module, title),
        SERVICES_DIR / f"{module}_service.py": render_service(module),
        PAGES_DIR / f"{module}.html": render_page(module, title),
        PARTIALS_DIR / f"{module}_table.html": render_table(module, title),
        PARTIALS_DIR / f"{module}_form.html": render_form_partial(module, title),
        TESTS_DIR / f"test_{module}_scaffold.py": render_test(module),
        REGISTRY_DIR / f"{module}.json": render_registry(module, title, group, url),
    }

    for path, content in files.items():
        write_file(path, content, force=args.force, dry_run=args.dry_run)

    print("完成：请手动在 app/main.py 引入并 include_router 新控制器。")


if __name__ == "__main__":
    main()
