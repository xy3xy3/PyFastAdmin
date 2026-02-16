"""后台导航注册与面包屑解析。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from app.apps.admin.registry import ADMIN_TREE, iter_leaf_nodes

NAV_GENERATED_DIR = Path(__file__).resolve().parent / "nav_generated"
DEFAULT_GROUP_ICON = "fa-solid fa-layer-group"
DEFAULT_ITEM_ICON = "fa-regular fa-circle-dot"

BASE_GROUP_META: dict[str, dict[str, Any]] = {
    "dashboard": {"name": "首页", "icon": "fa-solid fa-house", "order": 10},
    "security": {"name": "权限管理", "icon": "fa-solid fa-folder-tree", "order": 20},
    "accounts": {"name": "账号管理", "icon": "fa-solid fa-users-gear", "order": 30},
    "system": {"name": "系统工具", "icon": "fa-solid fa-screwdriver-wrench", "order": 40},
    "profile": {"name": "个人设置", "icon": "fa-regular fa-user", "order": 50},
}

BASE_ITEM_META: dict[str, dict[str, Any]] = {
    "dashboard_home": {
        "name": "仪表盘",
        "icon": "fa-solid fa-gauge-high",
        "match_prefixes": ["/admin/dashboard"],
        "order": 10,
    },
    "rbac": {"name": "RBAC 权限", "icon": "fa-solid fa-user-shield", "order": 10},
    "admin_users": {"name": "管理员管理", "icon": "fa-solid fa-users-gear", "group_key": "security", "order": 20},
    "profile": {"name": "个人资料", "icon": "fa-regular fa-id-card", "group_key": "profile", "order": 30},
    "password": {"name": "修改密码", "icon": "fa-solid fa-key", "group_key": "profile", "order": 40},
    "config": {"name": "系统配置", "icon": "fa-solid fa-gears", "order": 10},
    "operation_logs": {"name": "操作日志", "icon": "fa-solid fa-file-lines", "order": 20},
    "backup_config": {
        "name": "备份配置",
        "icon": "fa-solid fa-box-open",
        "menu_visible": False,
        "order": 25,
    },
    "backup_records": {
        "name": "数据备份",
        "icon": "fa-solid fa-database",
        "match_prefixes": ["/admin/backup"],
        "order": 30,
    },
}


def _normalize_path(path: str) -> str:
    """统一路径格式，避免尾斜杠影响匹配。"""

    normalized = str(path or "").strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}" if normalized else "/"
    normalized = normalized.rstrip("/")
    return normalized or "/"


def _normalize_prefixes(raw_prefixes: Any, fallback_url: str) -> list[str]:
    """清洗前缀列表，确保可用于 startswith 匹配。"""

    source = raw_prefixes if isinstance(raw_prefixes, list) else [fallback_url]
    prefixes: list[str] = []
    for item in source:
        normalized = _normalize_path(str(item or "").strip())
        if normalized not in prefixes:
            prefixes.append(normalized)
    return prefixes or ["/"]


def _normalize_icon(raw_icon: Any, default_icon: str) -> str:
    """规范化图标类名，空值时回退默认图标。"""

    icon = str(raw_icon or "").strip()
    return icon if icon else default_icon


def _normalize_generated_nav_node(payload: dict[str, Any]) -> dict[str, Any] | None:
    """清洗导航扩展配置，避免脏数据污染菜单。"""

    group_key = str(payload.get("group_key") or "").strip()
    node = payload.get("node")
    if not group_key or not isinstance(node, dict):
        return None

    resource = str(node.get("resource") or node.get("key") or "").strip()
    if not resource:
        return None

    normalized: dict[str, Any] = {
        "group_key": group_key,
        "resource": resource,
    }

    if "name" in node:
        normalized["name"] = str(node.get("name") or "").strip()
    if "url" in node:
        normalized["url"] = _normalize_path(str(node.get("url") or "").strip())
    if "icon" in node:
        normalized["icon"] = _normalize_icon(node.get("icon"), DEFAULT_ITEM_ICON)
    if "menu_visible" in node:
        normalized["menu_visible"] = bool(node.get("menu_visible"))
    if "order" in node:
        try:
            normalized["order"] = int(str(node.get("order")))
        except (TypeError, ValueError):
            pass
    if "match_prefixes" in node:
        normalized["match_prefixes"] = _normalize_prefixes(node.get("match_prefixes"), normalized.get("url", "/"))

    return normalized


def _load_generated_nav_nodes() -> list[dict[str, Any]]:
    """加载脚手架生成的导航扩展 JSON。"""

    if not NAV_GENERATED_DIR.exists():
        return []

    nodes: list[dict[str, Any]] = []
    for path in sorted(NAV_GENERATED_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        normalized = _normalize_generated_nav_node(payload)
        if normalized is not None:
            nodes.append(normalized)
    return nodes


def build_admin_nav_tree() -> list[dict[str, Any]]:
    """构建最终导航树：权限资源树 + 导航扩展配置。"""

    tree = copy.deepcopy(ADMIN_TREE)

    groups: dict[str, dict[str, Any]] = {}
    resources: dict[str, dict[str, Any]] = {}

    for group_index, group in enumerate(tree):
        group_key = str(group.get("key") or "").strip()
        group_name = str(group.get("name") or group_key).strip() or group_key
        if not group_key:
            continue

        meta = BASE_GROUP_META.get(group_key, {})
        groups[group_key] = {
            "key": group_key,
            "name": str(meta.get("name") or group_name),
            "icon": _normalize_icon(meta.get("icon"), DEFAULT_GROUP_ICON),
            "order": int(meta.get("order", (group_index + 1) * 10)),
            "items": [],
        }

        for item_index, node in enumerate(iter_leaf_nodes([group])):
            resource = str(node.get("key") or "").strip()
            if not resource:
                continue

            base_meta = BASE_ITEM_META.get(resource, {})
            target_group_key = str(base_meta.get("group_key") or group_key).strip() or group_key
            if target_group_key not in groups:
                target_meta = BASE_GROUP_META.get(target_group_key, {})
                groups[target_group_key] = {
                    "key": target_group_key,
                    "name": str(target_meta.get("name") or target_group_key),
                    "icon": _normalize_icon(target_meta.get("icon"), DEFAULT_GROUP_ICON),
                    "order": int(target_meta.get("order", 1000)),
                    "items": [],
                }
            node_url = _normalize_path(str(node.get("url") or "").strip())
            item_url = _normalize_path(str(base_meta.get("url") or node_url))

            item = {
                "resource": resource,
                "group_key": target_group_key,
                "name": str(base_meta.get("name") or node.get("name") or resource),
                "url": item_url,
                "icon": _normalize_icon(base_meta.get("icon"), DEFAULT_ITEM_ICON),
                "menu_visible": bool(base_meta.get("menu_visible", True)),
                "match_prefixes": _normalize_prefixes(base_meta.get("match_prefixes"), item_url),
                "order": int(base_meta.get("order", (item_index + 1) * 10)),
            }
            resources[resource] = item

    for override in _load_generated_nav_nodes():
        resource = override["resource"]
        item = resources.get(resource)
        if item is None:
            continue

        group_key = str(override.get("group_key") or item["group_key"]).strip()
        group = groups.get(group_key)
        if group is None:
            meta = BASE_GROUP_META.get(group_key, {})
            group = {
                "key": group_key,
                "name": str(meta.get("name") or group_key),
                "icon": _normalize_icon(meta.get("icon"), DEFAULT_GROUP_ICON),
                "order": int(meta.get("order", 1000)),
                "items": [],
            }
            groups[group_key] = group

        item["group_key"] = group_key
        if "name" in override and override["name"]:
            item["name"] = override["name"]
        if "url" in override and override["url"]:
            item["url"] = _normalize_path(override["url"])
        if "icon" in override and override["icon"]:
            item["icon"] = _normalize_icon(override["icon"], DEFAULT_ITEM_ICON)
        if "menu_visible" in override:
            item["menu_visible"] = bool(override["menu_visible"])
        if "order" in override:
            item["order"] = int(override["order"])
        if "match_prefixes" in override:
            item["match_prefixes"] = _normalize_prefixes(override["match_prefixes"], item["url"])
        else:
            item["match_prefixes"] = _normalize_prefixes(item.get("match_prefixes"), item["url"])

    for group in groups.values():
        group["items"] = []

    for item in resources.values():
        target_group = groups.get(item["group_key"])
        if target_group is None:
            continue
        target_group["items"].append(item)

    sorted_groups = sorted(groups.values(), key=lambda item: (item["order"], item["name"]))
    for group in sorted_groups:
        group["items"] = sorted(group["items"], key=lambda item: (item["order"], item["name"]))

    return sorted_groups


ADMIN_NAV_TREE = build_admin_nav_tree()


def _match_prefix_length(path: str, prefixes: list[str]) -> int:
    """返回最长匹配前缀长度，未命中时返回 -1。"""

    normalized_path = _normalize_path(path)
    best = -1
    for prefix in prefixes:
        normalized_prefix = _normalize_path(prefix)
        if normalized_path == normalized_prefix or normalized_path.startswith(f"{normalized_prefix}/"):
            best = max(best, len(normalized_prefix))
    return best


def build_navigation_context(path: str, permission_flags: dict[str, Any]) -> dict[str, Any]:
    """按当前路径和权限构建菜单与面包屑上下文。"""

    resources = permission_flags.get("resources", {}) if isinstance(permission_flags, dict) else {}
    matched_item: dict[str, Any] | None = None
    matched_group: dict[str, Any] | None = None
    matched_length = -1

    home_item: dict[str, Any] | None = None
    groups: list[dict[str, Any]] = []

    for group in ADMIN_NAV_TREE:
        visible_items: list[dict[str, Any]] = []
        group_active = False

        for item in group.get("items", []):
            resource = item["resource"]
            can_read = bool(resources.get(resource, {}).get("read", False))
            if not can_read:
                continue

            match_length = _match_prefix_length(path, item.get("match_prefixes", [item.get("url", "/")]))
            active = match_length >= 0
            if active:
                group_active = True
            if match_length > matched_length:
                matched_length = match_length
                matched_item = item
                matched_group = group

            item_payload = {
                "resource": resource,
                "name": item["name"],
                "url": item["url"],
                "icon": item["icon"],
                "active": active,
            }
            if item.get("menu_visible", True):
                visible_items.append(item_payload)

        if group["key"] == "dashboard":
            home_item = visible_items[0] if visible_items else None
            if home_item and matched_item is None:
                matched_item = home_item
                matched_group = group
            continue

        if not visible_items:
            continue

        groups.append(
            {
                "key": group["key"],
                "name": group["name"],
                "icon": group["icon"],
                "active": group_active,
                "items": visible_items,
            }
        )

    menu_open = {
        group["key"]: bool(group["active"])
        for group in groups
    }

    breadcrumb_parent = ""
    breadcrumb_title = home_item["name"] if home_item else "仪表盘"
    if matched_item:
        breadcrumb_title = matched_item["name"]
    if matched_item and matched_group and matched_group.get("key") != "dashboard":
        breadcrumb_parent = str(matched_group.get("name") or "")

    return {
        "home": home_item,
        "groups": groups,
        "menu_open": menu_open,
        "breadcrumb_parent": breadcrumb_parent,
        "breadcrumb_title": breadcrumb_title,
    }
