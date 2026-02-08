"""权限服务层。"""

from __future__ import annotations

from typing import Any

from beanie import PydanticObjectId

from app.models import RbacPermission
from app.models.rbac_permission import utc_now


async def list_permissions(role_slug: str, query: str | None = None) -> list[RbacPermission]:
    if query:
        regex = {"$regex": query, "$options": "i"}
        return (
            await RbacPermission.find(
                (RbacPermission.role_slug == role_slug)
                & (
                    (RbacPermission.resource == regex)
                    | (RbacPermission.action == regex)
                    | (RbacPermission.owner == regex)
                    | (RbacPermission.description == regex)
                )
            )
            .sort("-updated_at")
            .to_list()
        )
    return (
        await RbacPermission.find(RbacPermission.role_slug == role_slug)
        .sort("-updated_at")
        .to_list()
    )


async def get_permission(item_id: PydanticObjectId) -> RbacPermission | None:
    return await RbacPermission.get(item_id)


async def create_permission(payload: dict[str, Any]) -> RbacPermission:
    perm = RbacPermission(
        role_slug=payload["role_slug"],
        resource=payload["resource"],
        action=payload["action"],
        priority=payload["priority"],
        status=payload["status"],
        owner=payload.get("owner", ""),
        tags=payload.get("tags", []),
        description=payload.get("description", ""),
        updated_at=utc_now(),
    )
    await perm.insert()
    return perm


async def update_permission(perm: RbacPermission, payload: dict[str, Any]) -> RbacPermission:
    perm.resource = payload["resource"]
    perm.action = payload["action"]
    perm.priority = payload["priority"]
    perm.status = payload["status"]
    perm.owner = payload.get("owner", "")
    perm.tags = payload.get("tags", [])
    perm.description = payload.get("description", "")
    perm.updated_at = utc_now()
    await perm.save()
    return perm


async def delete_permission(perm: RbacPermission) -> None:
    await perm.delete()


async def get_role_permissions_map(role_slug: str) -> dict[str, set[str]]:
    items = await RbacPermission.find(RbacPermission.role_slug == role_slug).to_list()
    mapping: dict[str, set[str]] = {}
    for item in items:
        mapping.setdefault(item.resource, set()).add(item.action)
    return mapping


async def save_tree_permissions(
    role_slug: str,
    permissions: list[tuple[str, str, str]],
    owner: str,
) -> None:
    await RbacPermission.find(RbacPermission.role_slug == role_slug).delete()
    docs = []
    for resource, action, description in permissions:
        docs.append(
            RbacPermission(
                role_slug=role_slug,
                resource=resource,
                action=action,
                priority=3,
                status="enabled",
                owner=owner,
                tags=[],
                description=description,
                updated_at=utc_now(),
            )
        )
    if docs:
        await RbacPermission.insert_many(docs)
