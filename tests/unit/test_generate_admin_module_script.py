from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def scaffold_module():
    """加载脚手架脚本模块，便于直接验证模板渲染函数。"""

    script_path = Path('scripts/generate_admin_module.py')
    spec = importlib.util.spec_from_file_location('generate_admin_module', script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载脚手架脚本')

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_render_service_uses_set_literal(scaffold_module) -> None:
    """状态白名单应渲染为集合字面量，避免 f-string 误替换为元组字符串。"""

    rendered = scaffold_module.render_service('demo_inventory', 'DemoInventoryItem')

    assert 'if status not in {"enabled", "disabled"}:' in rendered
    assert "('enabled', 'disabled')" not in rendered


@pytest.mark.unit
def test_main_files_include_model(scaffold_module) -> None:
    """脚手架产物应包含模型文件路径。"""

    rendered = scaffold_module.render_test('demo_inventory')

    assert 'Path("app/models/demo_inventory.py").exists()' in rendered
