from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import Error, expect, sync_playwright


@pytest.mark.e2e
def test_rbac_roles_crud_flow_with_modal_and_htmx(e2e_base_url: str) -> None:
    """验证 RBAC 角色页面在浏览器中的新建、编辑、删除流程。"""

    admin_user = os.getenv("TEST_ADMIN_USER", "e2e_admin")
    admin_pass = os.getenv("TEST_ADMIN_PASS", "e2e_pass_123")
    suffix = str(int(time.time()))
    slug = f"fasthx_role_{suffix}"
    role_name = f"FastHX角色{suffix}"
    updated_name = f"{role_name}_已更新"

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Error as exc:
            pytest.skip(f"Chromium not installed for Playwright: {exc}")

        page = browser.new_page()
        page.goto(f"{e2e_base_url}/admin/login", wait_until="networkidle")
        page.locator("input[name=username]").fill(admin_user)
        page.locator("input[name=password]").fill(admin_pass)
        page.get_by_role("button", name="登录").click()
        page.wait_for_url("**/admin/dashboard")

        page.goto(f"{e2e_base_url}/admin/rbac", wait_until="networkidle")
        expect(page.get_by_role("heading", name="角色列表")).to_be_visible()

        page.locator("button:has-text('新建角色')").click()
        expect(page.locator("#modal-body")).to_contain_text("新建角色")
        page.locator("#modal-body input[name='name']").fill("A")
        page.locator("#modal-body input[name='slug']").fill(slug)
        page.locator("#modal-body input[name='description']").fill("E2E 角色")
        page.locator("#modal-body button[type='submit']").click()
        expect(page.locator("#modal-body")).to_contain_text("角色名称至少 2 个字符")

        page.locator("#modal-body input[name='name']").fill(role_name)
        page.locator("#modal-body button[type='submit']").click()

        page.locator("#role-search-form input[name='search_q']").fill(slug)
        page.get_by_role("button", name="搜索").click()
        expect(page.locator("#role-table")).to_contain_text(role_name)

        row = page.locator("#role-table tbody tr").filter(has_text=slug).first
        row.locator("button:has-text('编辑')").click()
        expect(page.locator("#modal-body")).to_contain_text("编辑角色")
        page.locator("#modal-body input[name='name']").fill(updated_name)
        page.locator("#modal-body button[type='submit']").click()
        expect(page.locator("#role-table")).to_contain_text(updated_name)

        row = page.locator("#role-table tbody tr").filter(has_text=slug).first
        page.once("dialog", lambda dialog: dialog.accept())
        row.locator("button:has-text('删除')").click()
        expect(page.locator("#role-table")).not_to_contain_text(slug)

        browser.close()
