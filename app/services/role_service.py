"""角色服务层。"""

from __future__ import annotations

from typing import Any

from app.apps.admin.registry import ADMIN_TREE, iter_leaf_nodes
from app.models import Role
from app.models.role import utc_now

DEFAULT_ROLES = [
    {"name": "超级管理员", "slug": "super"},
    {"name": "管理员", "slug": "admin"},
    {"name": "只读", "slug": "viewer"},
]


def build_default_role_permissions(role_slug: str, owner: str = "system") -> list[dict[str, Any]]:
    """根据默认角色构建权限集。"""

    if role_slug in {"super", "admin"}:
        action_picker = lambda actions: list(actions)
    elif role_slug == "viewer":
        action_picker = lambda actions: ["read"] if "read" in actions else []
    else:
        return []

    permissions: list[dict[str, Any]] = []
    for node in iter_leaf_nodes(ADMIN_TREE):
        actions = action_picker(node.get("actions", []))
        if not actions:
            continue
        description = f"{node['name']} | {node['url']}"
        for action in actions:
            permissions.append(
                {
                    "resource": node["key"],
                    "action": action,
                    "priority": 3,
                    "status": "enabled",
                    "owner": owner,
                    "tags": ["default"],
                    "description": description,
                }
            )

    return permissions


async def list_roles() -> list[Role]:
    return await Role.find_all().sort("slug").to_list()


async def get_role_by_slug(slug: str) -> Role | None:
    return await Role.find_one(Role.slug == slug)


async def create_role(payload: dict[str, Any]) -> Role:
    role = Role(
        name=payload["name"],
        slug=payload["slug"],
        status=payload.get("status", "enabled"),
        description=payload.get("description", ""),
        permissions=payload.get("permissions", []),
        updated_at=utc_now(),
    )
    await role.insert()
    return role


async def update_role(role: Role, payload: dict[str, Any]) -> Role:
    role.name = payload["name"]
    role.status = payload.get("status", role.status)
    role.description = payload.get("description", role.description)
    if "permissions" in payload:
        role.permissions = payload["permissions"]
    role.updated_at = utc_now()
    await role.save()
    return role


async def delete_role(role: Role) -> None:
    await role.delete()


async def ensure_default_roles() -> None:
    for item in DEFAULT_ROLES:
        default_permissions = build_default_role_permissions(item["slug"], owner="system")
        role = await get_role_by_slug(item["slug"])
        if not role:
            await create_role(
                {
                    "name": item["name"],
                    "slug": item["slug"],
                    "status": "enabled",
                    "description": "",
                    "permissions": default_permissions,
                }
            )
            continue

        if not role.permissions and default_permissions:
            role.permissions = default_permissions
            role.updated_at = utc_now()
            await role.save()
