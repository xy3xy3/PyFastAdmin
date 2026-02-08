"""后台页面注册表（用于权限树展示）。"""

from __future__ import annotations

from typing import Iterable

ADMIN_TREE = [
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
            }
        ],
    },
]


def iter_leaf_nodes(tree: list[dict]) -> Iterable[dict]:
    """遍历叶子节点。"""
    for node in tree:
        children = node.get("children")
        if children:
            yield from iter_leaf_nodes(children)
        else:
            yield node
