from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def scaffold_module():
    """加载脚手架脚本模块，便于直接验证模板渲染函数。"""

    script_path = Path("scripts/generate_admin_module.py")
    spec = importlib.util.spec_from_file_location("generate_admin_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载脚手架脚本")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_render_service_uses_set_literal(scaffold_module) -> None:
    """状态白名单应渲染为集合字面量，避免 f-string 误替换为元组字符串。"""

    rendered = scaffold_module.render_service("demo_inventory", "DemoInventoryItem")

    assert 'if status not in {"enabled", "disabled"}:' in rendered
    assert "('enabled', 'disabled')" not in rendered


@pytest.mark.unit
def test_main_files_include_model(scaffold_module) -> None:
    """脚手架产物应包含模型文件路径。"""

    rendered = scaffold_module.render_test("demo_inventory")

    assert 'Path("app/models/demo_inventory.py").exists()' in rendered


@pytest.mark.unit
def test_render_form_partial_targets_modal_body(scaffold_module) -> None:
    """脚手架表单应在弹窗内提交并回显错误。"""

    rendered = scaffold_module.render_form_partial("demo_inventory", "示例模块")

    assert 'hx-target="#modal-body"' in rendered
    assert 'hx-swap="innerHTML"' in rendered


@pytest.mark.unit
def test_render_form_partial_uses_fixed_header_footer_layout(scaffold_module) -> None:
    """脚手架弹窗应固定头部与底部，仅中间区域滚动。"""

    rendered = scaffold_module.render_form_partial("demo_inventory", "示例模块")

    assert 'max-height: calc(100vh - 9rem);' in rendered
    assert 'overflow-y-auto' in rendered
    assert 'border-b border-slate-100 pb-3' in rendered
    assert 'border-t border-slate-100 pt-3' in rendered


@pytest.mark.unit
def test_render_table_includes_bulk_delete_controls(scaffold_module) -> None:
    """脚手架表格应包含全选/反选和批量删除能力。"""

    rendered = scaffold_module.render_table("demo_inventory", "示例模块")

    assert 'data-bulk-scope' in rendered
    assert 'data-bulk-action="invert"' in rendered
    assert 'data-bulk-submit' in rendered
    assert 'data-bulk-bottom' in rendered
    assert 'data-bulk-overlay' in rendered
    assert 'hx-post="/admin/demo_inventory/bulk-delete"' in rendered
    assert 'hx-include="closest form"' in rendered
    assert 'hx-confirm="确认批量删除已勾选的记录吗？"' in rendered
    assert 'fa-rotate-right' in rendered
    assert "pagination.total" in rendered
    assert "pagination.pages" in rendered
    assert '"search_q": filters.search_q' in rendered
    assert '"page": pagination.page' in rendered


@pytest.mark.unit
def test_render_page_includes_default_search_form(scaffold_module) -> None:
    """脚手架页面应默认带关键词搜索和分页透传字段。"""

    rendered = scaffold_module.render_page("demo_inventory", "示例模块")

    assert 'id="demo_inventory-search-form"' in rendered
    assert 'hx-get="/admin/demo_inventory/table"' in rendered
    assert 'name="search_q"' in rendered
    assert 'name="page"' in rendered
    assert "x-model=\"search_q\"" in rendered
    assert "x-model=\"page\"" in rendered


@pytest.mark.unit
def test_render_controller_has_htmx_modal_error_strategy(scaffold_module) -> None:
    """脚手架控制器应内置 HTMX 弹窗错误回显策略。"""

    rendered = scaffold_module.render_controller("demo_inventory", "示例模块")

    assert "@fasthx_page(render_template_payload)" in rendered
    assert "set_form_error_status(response, request)" in rendered
    assert "set_hx_swap_headers(" in rendered
    assert '@jinja.page("partials/demo_inventory_table.html")' in rendered
    assert '@router.post("/demo_inventory/bulk-delete")' in rendered
    assert "parse_filters(values: Mapping[str, Any])" in rendered
    assert "build_pagination(len(filtered_items), page, PAGE_SIZE)" in rendered
    assert "request_values = await read_request_values(request)" in rendered


@pytest.mark.unit
def test_render_form_partial_keeps_filter_state(scaffold_module) -> None:
    """脚手架表单应回传筛选和分页参数，保证提交后列表状态不丢失。"""

    rendered = scaffold_module.render_form_partial("demo_inventory", "示例模块")

    assert 'name="search_q"' in rendered
    assert 'name="page"' in rendered


@pytest.mark.unit
def test_render_nav_registry_contains_resource_and_prefix(scaffold_module) -> None:
    """脚手架应输出导航注册文件，支持自动注入菜单与面包屑。"""

    rendered = scaffold_module.render_nav_registry("demo_inventory", "示例模块", "system", "/admin/demo_inventory")

    assert '"resource": "demo_inventory"' in rendered
    assert '"group_key": "system"' in rendered
    assert '"match_prefixes": [' in rendered
