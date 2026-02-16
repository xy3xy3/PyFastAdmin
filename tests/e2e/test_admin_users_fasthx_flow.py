from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import Error, expect, sync_playwright


@pytest.mark.e2e
def test_admin_users_crud_flow_with_modal_and_htmx(e2e_base_url: str) -> None:
    """验证管理员模块在浏览器中的新建、编辑、删除流程。"""

    admin_user = os.getenv("TEST_ADMIN_USER", "e2e_admin")
    admin_pass = os.getenv("TEST_ADMIN_PASS", "e2e_pass_123")
    suffix = str(int(time.time()))
    username = f"fasthx_admin_{suffix}"
    display_name = f"FastHX管理员{suffix}"
    updated_name = f"{display_name}_已更新"

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

        page.goto(f"{e2e_base_url}/admin/users", wait_until="networkidle")
        expect(page.get_by_role("heading", name="管理员列表")).to_be_visible()

        page.locator("button:has-text('新建管理员')").click()
        expect(page.locator("#modal-body")).to_contain_text("新建管理员")
        page.locator("#modal-body input[name='username']").fill(username)
        page.locator("#modal-body input[name='display_name']").fill(display_name)
        page.locator("#modal-body input[name='email']").fill(f"{username}@example.com")
        page.locator("#modal-body input[name='password']").fill("123")
        page.locator("#modal-body button[type='submit']").click()
        expect(page.locator("#modal-body")).to_contain_text("初始密码至少 6 位")

        page.locator("#modal-body input[name='password']").fill("e2e_pass_123")
        page.locator("#modal-body button[type='submit']").click()

        page.locator("#admin-search-form input[name='search_q']").fill(username)
        page.get_by_role("button", name="搜索").click()
        expect(page.locator("#admin-table")).to_contain_text(display_name)

        row = page.locator("#admin-table tbody tr").filter(has_text=username).first
        row.locator("button:has-text('编辑')").click()
        expect(page.locator("#modal-body")).to_contain_text("编辑管理员")
        name_input = page.locator("#modal-body input[name='display_name']")
        name_input.fill(updated_name)
        page.locator("#modal-body button[type='submit']").click()
        expect(page.locator("#admin-table")).to_contain_text(updated_name)

        row = page.locator("#admin-table tbody tr").filter(has_text=username).first
        page.once("dialog", lambda dialog: dialog.accept())
        row.locator("button:has-text('删除')").click()
        expect(page.locator("#admin-table")).not_to_contain_text(username)

        browser.close()
