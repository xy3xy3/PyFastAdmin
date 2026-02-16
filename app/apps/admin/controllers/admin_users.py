"""管理员管理控制器。"""

from __future__ import annotations

from typing import Any, Mapping

from beanie import PydanticObjectId
from fasthx import page as fasthx_page
from fastapi import APIRouter, Form, HTTPException, Request, Response

from app.apps.admin.rendering import (
    TemplatePayload,
    base_context,
    build_pagination,
    jinja,
    parse_positive_int,
    read_request_values,
    render_template_payload,
    set_form_error_status,
    set_hx_swap_headers,
)
from app.services import admin_user_service, auth_service, log_service, permission_decorator, role_service, validators

router = APIRouter(prefix="/admin")

STATUS_META: dict[str, dict[str, str]] = {
    "enabled": {"label": "启用", "color": "#2f855a"},
    "disabled": {"label": "禁用", "color": "#b7791f"},
}

ADMIN_SORT_OPTIONS: dict[str, str] = {
    "updated_desc": "最近更新",
    "updated_asc": "最早更新",
    "username_asc": "账号 A-Z",
}

ADMIN_PAGE_SIZE = 10


def build_form_data(values: dict[str, Any]) -> dict[str, Any]:
    """构建管理员表单默认值。"""

    return {
        "username": values.get("username", ""),
        "display_name": values.get("display_name", ""),
        "email": values.get("email", ""),
        "role_slug": values.get("role_slug", "admin"),
        "status": values.get("status", "enabled"),
        "password": values.get("password", ""),
    }


def form_errors(values: dict[str, Any], is_create: bool, role_slugs: set[str]) -> list[str]:
    """统一校验管理员表单字段，降低二开重复校验成本。"""

    errors: list[str] = []

    username_error = validators.validate_admin_username(str(values.get("username", "")))
    if username_error:
        errors.append(username_error)

    email_error = validators.validate_optional_email(str(values.get("email", "")))
    if email_error:
        errors.append(email_error)

    if len(str(values.get("display_name", ""))) < 2:
        errors.append("显示名称至少 2 个字符")
    if values.get("status") not in STATUS_META:
        errors.append("状态不合法")
    if role_slugs and values.get("role_slug") not in role_slugs:
        errors.append("角色不合法")
    if is_create and len(values.get("password", "")) < 6:
        errors.append("初始密码至少 6 位")
    return errors


def parse_admin_filters(values: Mapping[str, Any]) -> tuple[dict[str, str], int]:
    """解析管理员列表筛选条件。"""

    search_q = str(values.get("search_q") or values.get("q") or "").strip()
    search_role = str(values.get("search_role") or "").strip()
    search_status = str(values.get("search_status") or "").strip()
    if search_status not in STATUS_META:
        search_status = ""

    search_sort = str(values.get("search_sort") or "updated_desc").strip()
    if search_sort not in ADMIN_SORT_OPTIONS:
        search_sort = "updated_desc"

    page = parse_positive_int(values.get("page"), default=1)
    return (
        {
            "search_q": search_q,
            "search_role": search_role,
            "search_status": search_status,
            "search_sort": search_sort,
        },
        page,
    )


def filter_admin_items(items: list[Any], filters: dict[str, str]) -> list[Any]:
    """按筛选条件过滤与排序管理员列表。"""

    filtered = items
    if filters["search_role"]:
        filtered = [item for item in filtered if item.role_slug == filters["search_role"]]
    if filters["search_status"]:
        filtered = [item for item in filtered if item.status == filters["search_status"]]

    sort_key = filters["search_sort"]
    if sort_key == "updated_asc":
        filtered = sorted(filtered, key=lambda item: item.updated_at)
    elif sort_key == "username_asc":
        filtered = sorted(filtered, key=lambda item: item.username.lower())
    else:
        filtered = sorted(filtered, key=lambda item: item.updated_at, reverse=True)
    return filtered


async def build_admin_table_context(
    request: Request,
    filters: dict[str, str],
    page: int,
) -> dict[str, Any]:
    """构建管理员表格上下文。"""

    roles = await role_service.list_roles()
    role_map = {item.slug: item.name for item in roles}
    items = await admin_user_service.list_admins(filters["search_q"] or None)
    filtered_items = filter_admin_items(items, filters)
    pagination = build_pagination(len(filtered_items), page, ADMIN_PAGE_SIZE)
    start = (pagination["page"] - 1) * ADMIN_PAGE_SIZE
    paged_items = filtered_items[start : start + ADMIN_PAGE_SIZE]

    return {
        **base_context(request),
        "items": paged_items,
        "status_meta": STATUS_META,
        "role_map": role_map,
        "roles": roles,
        "filters": filters,
        "pagination": pagination,
    }


@router.get("/users")
@jinja.page("pages/admin_users.html")
async def admin_users_page(request: Request) -> dict[str, Any]:
    """管理员页面。"""

    filters, page = parse_admin_filters(request.query_params)
    context = await build_admin_table_context(request, filters, page)
    context["admin_sort_options"] = ADMIN_SORT_OPTIONS
    await log_service.record_request(
        request,
        action="read",
        module="admin_users",
        target="管理员账号",
        detail="访问管理员管理页面",
    )
    return context


@router.get("/users/table")
@jinja.page("partials/admin_users_table.html")
async def admin_users_table(request: Request) -> dict[str, Any]:
    """管理员表格 partial。"""

    filters, page = parse_admin_filters(request.query_params)
    return await build_admin_table_context(request, filters, page)


@router.get("/users/new")
@jinja.page("partials/admin_users_form.html")
async def admin_users_new(request: Request) -> dict[str, Any]:
    """新建管理员弹窗。"""

    roles = await role_service.list_roles()
    default_slug = roles[0].slug if roles else "admin"
    form = build_form_data({"role_slug": default_slug})
    filters, page = parse_admin_filters(request.query_params)
    context = {
        **base_context(request),
        "mode": "create",
        "action": "/admin/users",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "roles": roles,
        "filters": filters,
        "page": page,
    }
    return context


@router.get("/users/{item_id}/edit")
@jinja.page("partials/admin_users_form.html")
async def admin_users_edit(request: Request, item_id: PydanticObjectId) -> dict[str, Any]:
    """编辑管理员弹窗。"""

    item = await admin_user_service.get_admin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="账号不存在")

    roles = await role_service.list_roles()
    form = build_form_data(
        {
            "username": item.username,
            "display_name": item.display_name,
            "email": item.email,
            "role_slug": item.role_slug,
            "status": item.status,
            "password": "",
        }
    )
    filters, page = parse_admin_filters(request.query_params)
    context = {
        **base_context(request),
        "mode": "edit",
        "action": f"/admin/users/{item_id}",
        "form": form,
        "errors": [],
        "status_meta": STATUS_META,
        "roles": roles,
        "filters": filters,
        "page": page,
    }
    return context


@router.post("/users")
@permission_decorator.permission_meta("admin_users", "create")
@fasthx_page(render_template_payload)
async def admin_users_create(
    request: Request,
    response: Response,
    username: str = Form(""),
    display_name: str = Form(""),
    email: str = Form(""),
    role_slug: str = Form("admin"),
    status: str = Form("enabled"),
    password: str = Form(""),
) -> TemplatePayload:
    """创建管理员。"""

    request_values = await read_request_values(request)
    filters, page = parse_admin_filters(request_values)
    roles = await role_service.list_roles()
    role_slugs = {item.slug for item in roles}
    form = build_form_data(
        {
            "username": validators.normalize_admin_username(username),
            "display_name": display_name.strip(),
            "email": validators.normalize_email(email),
            "role_slug": role_slug,
            "status": status,
            "password": password,
        }
    )

    errors = form_errors(form, is_create=True, role_slugs=role_slugs)
    if await admin_user_service.get_admin_by_username(form["username"]):
        errors.append("账号已存在")

    if errors:
        context = {
            **base_context(request),
            "mode": "create",
            "action": "/admin/users",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "roles": roles,
            "filters": filters,
            "page": page,
        }
        set_form_error_status(response, request)
        return TemplatePayload(
            template="partials/admin_users_form.html",
            context=context,
        )

    payload = {
        "username": form["username"],
        "display_name": form["display_name"],
        "email": form["email"],
        "role_slug": form["role_slug"],
        "status": form["status"],
        "password_hash": auth_service.hash_password(form["password"]),
    }
    created = await admin_user_service.create_admin(payload)
    await log_service.record_request(
        request,
        action="create",
        module="admin_users",
        target=f"管理员: {created.display_name}",
        target_id=str(created.id),
        detail=f"创建管理员账号 {created.username}",
    )

    set_hx_swap_headers(
        response,
        target="#admin-table",
        trigger={
            "admin-toast": {
                "title": "已创建",
                "message": "管理员账号已保存",
                "variant": "success",
            },
            "rbac-close": True,
        },
    )
    context = await build_admin_table_context(request, filters, page)
    return TemplatePayload(
        template="partials/admin_users_table.html",
        context=context,
    )


@router.post("/users/bulk-delete")
@permission_decorator.permission_meta("admin_users", "delete")
@jinja.page("partials/admin_users_table.html")
async def admin_users_bulk_delete(request: Request, response: Response) -> dict[str, Any]:
    """批量删除管理员账号。"""

    request_values = await read_request_values(request)
    filters, page = parse_admin_filters(request_values)
    form_data = await request.form()
    selected_ids = [str(item).strip() for item in form_data.getlist("selected_ids") if str(item).strip()]
    selected_ids = list(dict.fromkeys(selected_ids))

    current_admin_id = str(request.session.get("admin_id") or "")
    deleted_count = 0
    skipped_self = 0
    skipped_invalid = 0

    for raw_id in selected_ids:
        try:
            object_id = PydanticObjectId(raw_id)
        except Exception:
            skipped_invalid += 1
            continue

        item = await admin_user_service.get_admin(object_id)
        if not item:
            skipped_invalid += 1
            continue

        if str(item.id) == current_admin_id:
            skipped_self += 1
            continue

        await admin_user_service.delete_admin(item)
        deleted_count += 1
        await log_service.record_request(
            request,
            action="delete",
            module="admin_users",
            target=f"管理员: {item.display_name}",
            target_id=str(item.id),
            detail=f"批量删除管理员账号 {item.username}",
        )

    if deleted_count == 0:
        toast_message = "未删除任何账号，请先勾选记录"
    else:
        extras: list[str] = []
        if skipped_self:
            extras.append(f"跳过当前账号 {skipped_self} 条")
        if skipped_invalid:
            extras.append(f"跳过无效记录 {skipped_invalid} 条")
        suffix = f"（{'，'.join(extras)}）" if extras else ""
        toast_message = f"已删除 {deleted_count} 条管理员账号{suffix}"

    set_hx_swap_headers(
        response,
        target="#admin-table",
        trigger={
            "admin-toast": {
                "title": "批量删除完成",
                "message": toast_message,
                "variant": "warning",
            }
        },
    )
    return await build_admin_table_context(request, filters, page)


@router.post("/users/{item_id}")
@permission_decorator.permission_meta("admin_users", "update")
@fasthx_page(render_template_payload)
async def admin_users_update(
    request: Request,
    response: Response,
    item_id: PydanticObjectId,
    display_name: str = Form(""),
    email: str = Form(""),
    role_slug: str = Form("admin"),
    status: str = Form("enabled"),
    password: str = Form(""),
) -> TemplatePayload:
    """更新管理员。"""

    request_values = await read_request_values(request)
    filters, page = parse_admin_filters(request_values)
    item = await admin_user_service.get_admin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="账号不存在")

    roles = await role_service.list_roles()
    role_slugs = {item.slug for item in roles}
    form = build_form_data(
        {
            "username": item.username,
            "display_name": display_name.strip(),
            "email": validators.normalize_email(email),
            "role_slug": role_slug,
            "status": status,
            "password": password,
        }
    )

    errors = form_errors(form, is_create=False, role_slugs=role_slugs)
    if errors:
        context = {
            **base_context(request),
            "mode": "edit",
            "action": f"/admin/users/{item_id}",
            "form": form,
            "errors": errors,
            "status_meta": STATUS_META,
            "roles": roles,
            "filters": filters,
            "page": page,
        }
        set_form_error_status(response, request)
        return TemplatePayload(
            template="partials/admin_users_form.html",
            context=context,
        )

    payload = {
        "display_name": form["display_name"],
        "email": form["email"],
        "role_slug": form["role_slug"],
        "status": form["status"],
        "password_hash": auth_service.hash_password(form["password"]) if form["password"] else "",
    }
    await admin_user_service.update_admin(item, payload)
    await log_service.record_request(
        request,
        action="update",
        module="admin_users",
        target=f"管理员: {item.display_name}",
        target_id=str(item.id),
        detail=f"更新管理员账号 {item.username}",
    )
    if str(item.id) == str(request.session.get("admin_id")):
        request.session["admin_name"] = item.display_name

    set_hx_swap_headers(
        response,
        target="#admin-table",
        trigger={
            "admin-toast": {
                "title": "已更新",
                "message": "管理员账号已修改",
                "variant": "success",
            },
            "rbac-close": True,
        },
    )
    context = await build_admin_table_context(request, filters, page)
    return TemplatePayload(
        template="partials/admin_users_table.html",
        context=context,
    )


@router.delete("/users/{item_id}")
@permission_decorator.permission_meta("admin_users", "delete")
@jinja.page("partials/admin_users_table.html")
async def admin_users_delete(request: Request, response: Response, item_id: PydanticObjectId) -> dict[str, Any]:
    """删除管理员。"""

    request_values = await read_request_values(request)
    filters, page = parse_admin_filters(request_values)
    item = await admin_user_service.get_admin(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="账号不存在")

    if str(item.id) == str(request.session.get("admin_id")):
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    await admin_user_service.delete_admin(item)
    await log_service.record_request(
        request,
        action="delete",
        module="admin_users",
        target=f"管理员: {item.display_name}",
        target_id=str(item.id),
        detail=f"删除管理员账号 {item.username}",
    )
    set_hx_swap_headers(
        response,
        target="#admin-table",
        trigger={
            "admin-toast": {
                "title": "已删除",
                "message": "管理员账号已移除",
                "variant": "warning",
            }
        },
    )
    return await build_admin_table_context(request, filters, page)
