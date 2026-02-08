"""角色服务层。"""

from __future__ import annotations

from typing import Any

from app.models import Role
from app.models.role import utc_now

DEFAULT_ROLES = [
    {"name": "超级管理员", "slug": "super"},
    {"name": "管理员", "slug": "admin"},
    {"name": "只读", "slug": "viewer"},
]


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
        updated_at=utc_now(),
    )
    await role.insert()
    return role


async def update_role(role: Role, payload: dict[str, Any]) -> Role:
    role.name = payload["name"]
    role.status = payload.get("status", role.status)
    role.description = payload.get("description", role.description)
    role.updated_at = utc_now()
    await role.save()
    return role


async def delete_role(role: Role) -> None:
    await role.delete()


async def ensure_default_roles() -> None:
    for item in DEFAULT_ROLES:
        if not await get_role_by_slug(item["slug"]):
            await create_role(
                {
                    "name": item["name"],
                    "slug": item["slug"],
                    "status": "enabled",
                    "description": "",
                }
            )
