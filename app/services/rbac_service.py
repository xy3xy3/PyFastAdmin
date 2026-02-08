"""RBAC 服务层。"""

from __future__ import annotations

from typing import Any

from beanie import PydanticObjectId

from app.models import RbacPolicy
from app.models.rbac import utc_now


async def list_policies(query: str | None = None) -> list[RbacPolicy]:
    if query:
        regex = {"$regex": query, "$options": "i"}
        return (
            await RbacPolicy.find(
                {
                    "$or": [
                        {"role_name": regex},
                        {"role_key": regex},
                        {"resource": regex},
                        {"action": regex},
                        {"owner": regex},
                    ]
                }
            )
            .sort("-updated_at")
            .to_list()
        )
    return await RbacPolicy.find_all().sort("-updated_at").to_list()


async def get_policy(item_id: PydanticObjectId) -> RbacPolicy | None:
    return await RbacPolicy.get(item_id)


async def create_policy(payload: dict[str, Any]) -> RbacPolicy:
    policy = RbacPolicy(
        role_key=payload["role_key"],
        role_name=payload["role_name"],
        resource=payload["resource"],
        action=payload["action"],
        owner=payload["owner"],
        priority=payload["priority"],
        status=payload["status"],
        tags=payload["tags"],
        description=payload["description"],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    await policy.insert()
    return policy


async def update_policy(policy: RbacPolicy, payload: dict[str, Any]) -> RbacPolicy:
    policy.role_key = payload["role_key"]
    policy.role_name = payload["role_name"]
    policy.resource = payload["resource"]
    policy.action = payload["action"]
    policy.owner = payload["owner"]
    policy.priority = payload["priority"]
    policy.status = payload["status"]
    policy.tags = payload["tags"]
    policy.description = payload["description"]
    policy.updated_at = utc_now()
    await policy.save()
    return policy


async def delete_policy(policy: RbacPolicy) -> None:
    await policy.delete()
