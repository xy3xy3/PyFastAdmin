from __future__ import annotations

import os

import pytest
from playwright.sync_api import Error, sync_playwright


@pytest.mark.e2e
def test_admin_can_login_and_open_core_pages(e2e_base_url: str) -> None:
    admin_user = os.getenv("TEST_ADMIN_USER", "e2e_admin")
    admin_pass = os.getenv("TEST_ADMIN_PASS", "e2e_pass_123")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Error as exc:
            pytest.skip(f"Chromium not installed for Playwright: {exc}")

        page = browser.new_page()

        page.goto(f"{e2e_base_url}/admin/login", wait_until="networkidle")
        page.get_by_label("账号").fill(admin_user)
        page.get_by_label("密码").fill(admin_pass)
        page.get_by_role("button", name="登录").click()

        page.wait_for_url("**/admin/dashboard")
        page.goto(f"{e2e_base_url}/admin/users", wait_until="networkidle")
        expect_text = page.locator("text=管理员列表")
        assert expect_text.is_visible()

        page.goto(f"{e2e_base_url}/admin/config", wait_until="networkidle")
        assert page.locator("text=站点设置").is_visible()

        page.goto(f"{e2e_base_url}/admin/logs", wait_until="networkidle")
        assert page.locator("text=操作日志").is_visible()

        browser.close()
