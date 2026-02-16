from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from playwright.sync_api import Error, expect, sync_playwright
from pymongo import MongoClient


def _utc_now() -> datetime:
    """返回 UTC 时间，便于构造日志测试数据。"""

    return datetime.now(timezone.utc)


@pytest.mark.e2e
def test_logs_page_search_and_delete_with_htmx_in_browser(
    e2e_base_url: str,
    test_mongo_url: str,
    e2e_mongo_db_name: str,
) -> None:
    """验证 logs 页面在浏览器中的搜索与删除交互可用。"""

    target_to_delete = "E2E-FastHX-Delete-Target"
    target_to_keep = "E2E-FastHX-Keep-Target"

    mongo_client = MongoClient(test_mongo_url)
    db = mongo_client[e2e_mongo_db_name]
    db.operation_logs.insert_many(
        [
            {
                "action": "delete",
                "module": "logs",
                "target": target_to_delete,
                "target_id": "e2e-1",
                "detail": "E2E 删除目标日志",
                "operator": "e2e",
                "method": "DELETE",
                "path": "/admin/logs/e2e-1",
                "ip": "127.0.0.1",
                "created_at": _utc_now(),
            },
            {
                "action": "create",
                "module": "logs",
                "target": target_to_keep,
                "target_id": "e2e-2",
                "detail": "E2E 保留目标日志",
                "operator": "e2e",
                "method": "POST",
                "path": "/admin/logs/e2e-2",
                "ip": "127.0.0.1",
                "created_at": _utc_now(),
            },
        ]
    )
    mongo_client.close()

    admin_user = os.getenv("TEST_ADMIN_USER", "e2e_admin")
    admin_pass = os.getenv("TEST_ADMIN_PASS", "e2e_pass_123")

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

        page.goto(f"{e2e_base_url}/admin/logs", wait_until="networkidle")
        expect(page.get_by_role("heading", name="操作日志")).to_be_visible()

        page.locator("#logs-search-form input[name='search_q']").fill(target_to_delete)
        page.get_by_role("button", name="搜索").click()
        expect(page.locator("#logs-table")).to_contain_text(target_to_delete)

        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#logs-table button:has-text('删除')").first.click()
        expect(page.locator("#logs-table")).not_to_contain_text(target_to_delete)

        page.locator("#logs-search-form input[name='search_q']").fill(target_to_keep)
        page.get_by_role("button", name="搜索").click()
        expect(page.locator("#logs-table")).to_contain_text(target_to_keep)

        browser.close()
