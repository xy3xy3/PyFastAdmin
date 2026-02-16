from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import Error, expect, sync_playwright


@pytest.mark.e2e
def test_auth_profile_and_password_flow_in_browser(e2e_base_url: str) -> None:
    """验证个人资料与修改密码页面在浏览器中的可用性。"""

    admin_user = os.getenv("TEST_ADMIN_USER", "e2e_admin")
    admin_pass = os.getenv("TEST_ADMIN_PASS", "e2e_pass_123")
    new_password = "e2e_new_pass_456"
    suffix = str(int(time.time()))
    new_display_name = f"E2E管理员{suffix}"
    new_email = f"e2e_{suffix}@example.com"

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

        page.goto(f"{e2e_base_url}/admin/profile", wait_until="networkidle")
        expect(page.get_by_role("heading", name="个人资料")).to_be_visible()
        page.locator("input[name='email']").fill("invalid-email")
        page.get_by_role("button", name="保存资料").click()
        expect(page.locator("text=邮箱格式不合法")).to_be_visible()

        page.locator("input[name='display_name']").fill(new_display_name)
        page.locator("input[name='email']").fill(new_email)
        page.get_by_role("button", name="保存资料").click()
        expect(page.locator("text=已保存最新资料。")).to_be_visible()
        expect(page.locator("input[name='display_name']")).to_have_value(new_display_name)

        page.goto(f"{e2e_base_url}/admin/password", wait_until="networkidle")
        expect(page.get_by_role("heading", name="修改密码")).to_be_visible()
        page.locator("input[name='old_password']").fill(admin_pass)
        page.locator("input[name='new_password']").fill("123")
        page.locator("input[name='confirm_password']").fill("123")
        page.get_by_role("button", name="更新密码").click()
        expect(page.locator("text=新密码至少 6 位。")).to_be_visible()

        page.locator("input[name='old_password']").fill(admin_pass)
        page.locator("input[name='new_password']").fill(new_password)
        page.locator("input[name='confirm_password']").fill("not_match")
        page.get_by_role("button", name="更新密码").click()
        expect(page.locator("text=两次输入的密码不一致。")).to_be_visible()

        page.locator("input[name='old_password']").fill("wrong_password")
        page.locator("input[name='new_password']").fill(new_password)
        page.locator("input[name='confirm_password']").fill(new_password)
        page.get_by_role("button", name="更新密码").click()
        expect(page.locator("text=旧密码不正确。")).to_be_visible()

        page.locator("input[name='old_password']").fill(admin_pass)
        page.locator("input[name='new_password']").fill(new_password)
        page.locator("input[name='confirm_password']").fill(new_password)
        page.get_by_role("button", name="更新密码").click()
        expect(page.locator("text=密码已更新，请妥善保存。")).to_be_visible()

        page.goto(f"{e2e_base_url}/admin/logout", wait_until="networkidle")
        page.locator("input[name=username]").fill(admin_user)
        page.locator("input[name=password]").fill(new_password)
        page.get_by_role("button", name="登录").click()
        page.wait_for_url("**/admin/dashboard")

        browser.close()
