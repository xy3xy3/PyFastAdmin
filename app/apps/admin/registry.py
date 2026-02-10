"""后台页面注册表（用于权限树展示）。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

VALID_ACTIONS = {"create", "read", "update", "delete"}
REGISTRY_GENERATED_DIR = Path(__file__).resolve().parent / "registry_generated"

BASE_ADMIN_TREE = [
    {
        "key": "dashboard",
        "name": "首页",
        "children": [
            {
                "key": "dashboard_home",
                "name": "仪表盘",
                "url": "/admin/dashboard",
                "actions": ["read"],
            }
        ],
    },
    {
        "key": "security",
        "name": "权限与安全",
        "children": [
            {
                "key": "rbac",
                "name": "角色与权限",
                "url": "/admin/rbac",
                "actions": ["create", "read", "update", "delete"],
            }
        ],
    },
    {
        "key": "accounts",
        "name": "账号管理",
        "children": [
            {
                "key": "admin_users",
                "name": "管理员账号",
                "url": "/admin/users",
                "actions": ["create", "read", "update", "delete"],
            },
            {
                "key": "profile",
                "name": "个人资料",
                "url": "/admin/profile",
                "actions": ["read", "update"],
            },
            {
                "key": "password",
                "name": "修改密码",
                "url": "/admin/password",
                "actions": ["read", "update"],
            },
        ],
    },
    {
        "key": "system",
        "name": "系统设置",
        "children": [
            {
                "key": "config",
                "name": "系统配置",
                "url": "/admin/config",
                "actions": ["read", "update"],
            },
            {
                "key": "operation_logs",
                "name": "操作日志",
                "url": "/admin/logs",
                "actions": ["read"],
            },
            {
                "key": "backup",
                "name": "数据备份",
                "url": "/admin/backup",
                "actions": ["create", "read", "update", "delete"],
            },
        ],
    },
]


def _normalize_generated_node(payload: dict[str, Any]) -> dict[str, Any] | None:
    """清洗外部注册节点，避免脏数据污染权限树。"""

    group_key = str(payload.get("group_key") or "").strip()
    node = payload.get("node")
    if not group_key or not isinstance(node, dict):
        return None

    key = str(node.get("key") or "").strip()
    name = str(node.get("name") or "").strip()
    url = str(node.get("url") or "").strip()
    actions = [
        str(action).strip().lower()
        for action in node.get("actions", [])
        if str(action).strip().lower() in VALID_ACTIONS
    ]

    if not key or not name or not url or not actions:
        return None

    normalized = {
        "group_key": group_key,
        "node": {
            "key": key,
            "name": name,
            "url": url,
            "actions": list(dict.fromkeys(actions)),
        },
    }
    return normalized


def _load_generated_nodes() -> list[dict[str, Any]]:
    """加载脚手架生成的注册节点（JSON）。"""

    if not REGISTRY_GENERATED_DIR.exists():
        return []

    nodes: list[dict[str, Any]] = []
    for path in sorted(REGISTRY_GENERATED_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        normalized = _normalize_generated_node(payload)
        if normalized is not None:
            nodes.append(normalized)
    return nodes


def build_admin_tree() -> list[dict[str, Any]]:
    """构建最终权限树：基础树 + 脚手架扩展。"""

    tree = copy.deepcopy(BASE_ADMIN_TREE)
    group_map = {
        str(group.get("key") or ""): group
        for group in tree
    }

    for item in _load_generated_nodes():
        group_key = item["group_key"]
        group = group_map.get(group_key)
        if not group:
            group = {"key": group_key, "name": group_key, "children": []}
            tree.append(group)
            group_map[group_key] = group

        children = group.setdefault("children", [])
        existing_index = next(
            (index for index, child in enumerate(children) if child.get("key") == item["node"]["key"]),
            None,
        )
        if existing_index is None:
            children.append(item["node"])
        else:
            children[existing_index] = item["node"]

    return tree


ADMIN_TREE = build_admin_tree()


def iter_leaf_nodes(tree: list[dict]) -> Iterable[dict]:
    """遍历叶子节点。"""

    for node in tree:
        children = node.get("children")
        if children:
            yield from iter_leaf_nodes(children)
        else:
            yield node
