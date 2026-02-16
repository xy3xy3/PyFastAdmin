from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import Error, expect, sync_playwright


@pytest.mark.e2e
def test_config_page_can_save_backup_tab_settings_in_browser(e2e_base_url: str) -> None:
    """验证 config 页面在浏览器中切换页签并保存配置。"""

    admin_user = os.getenv("TEST_ADMIN_USER", "e2e_admin")
    admin_pass = os.getenv("TEST_ADMIN_PASS", "e2e_pass_123")
    local_dir = f"backups/e2e_config_{int(time.time())}"

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

        page.goto(f"{e2e_base_url}/admin/config", wait_until="networkidle")
        expect(page.get_by_role("heading", name="系统配置")).to_be_visible()

        page.get_by_role("button", name="备份设置").click()
        backup_dir_input = page.locator("input[name='backup_local_dir']")
        expect(backup_dir_input).to_be_visible()
        backup_dir_input.fill(local_dir)

        page.get_by_role("button", name="保存设置").click()
        expect(page.locator("text=配置已保存。")).to_be_visible()
        expect(page.locator("input[name='config_tab']")).to_have_value("backup")
        expect(page.locator("input[name='backup_local_dir']")).to_have_value(local_dir)

        browser.close()
