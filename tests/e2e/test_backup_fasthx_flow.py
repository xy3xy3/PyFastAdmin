from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from playwright.sync_api import Error, expect, sync_playwright
from pymongo import MongoClient


def _utc_now() -> datetime:
    """返回 UTC 当前时间。"""

    return datetime.now(timezone.utc)


@pytest.mark.e2e
def test_backup_page_delete_record_with_htmx_in_browser(
    e2e_base_url: str,
    test_mongo_url: str,
    e2e_mongo_db_name: str,
) -> None:
    """验证 backup 页面在浏览器中的 HTMX 删除流程。"""

    target_file = "e2e_backup_delete_target.tar.gz"
    keep_file = "e2e_backup_keep_target.tar.gz"

    mongo_client = MongoClient(test_mongo_url)
    db = mongo_client[e2e_mongo_db_name]
    now = _utc_now()
    db.backup_records.insert_many(
        [
            {
                "filename": target_file,
                "size": 123456,
                "status": "success",
                "collections": ["admin_users"],
                "cloud_uploads": [],
                "error": "",
                "started_at": now - timedelta(minutes=1),
                "finished_at": now,
                "created_at": now,
            },
            {
                "filename": keep_file,
                "size": 654321,
                "status": "failed",
                "collections": ["operation_logs"],
                "cloud_uploads": [],
                "error": "simulated",
                "started_at": now - timedelta(minutes=2),
                "finished_at": now - timedelta(minutes=1),
                "created_at": now - timedelta(minutes=1),
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

        page.goto(f"{e2e_base_url}/admin/backup", wait_until="networkidle")
        expect(page.get_by_role("heading", name="数据备份")).to_be_visible()
        expect(page.locator("#backup-table")).to_contain_text(target_file)

        page.once("dialog", lambda dialog: dialog.accept())
        row = page.locator("#backup-table tbody tr").filter(has_text=target_file).first
        row.locator("button:has-text('删除')").click()

        expect(page.locator("#backup-table")).not_to_contain_text(target_file)
        expect(page.locator("#backup-table")).to_contain_text(keep_file)
        expect(page.locator("#backup-table")).to_contain_text("删除备份记录成功")

        browser.close()
