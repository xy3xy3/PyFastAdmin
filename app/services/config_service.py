"""系统配置服务层。"""

from __future__ import annotations

from app.models import ConfigItem
from app.models.config_item import utc_now

SMTP_DEFAULTS = {
    "smtp_host": "smtp.example.com",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_pass": "",
    "smtp_from": "no-reply@example.com",
    "smtp_ssl": "false",
}

SMTP_META = {
    "smtp_host": "SMTP 主机",
    "smtp_port": "SMTP 端口",
    "smtp_user": "SMTP 用户名",
    "smtp_pass": "SMTP 密码",
    "smtp_from": "发件人地址",
    "smtp_ssl": "启用 SSL (true/false)",
}


async def get_smtp_config() -> dict[str, str]:
    items = await ConfigItem.find(ConfigItem.group == "smtp").to_list()
    mapping = {item.key: item.value for item in items}
    merged = SMTP_DEFAULTS | mapping
    return merged


async def save_smtp_config(payload: dict[str, str]) -> None:
    for key, name in SMTP_META.items():
        value = payload.get(key, "").strip()
        item = await ConfigItem.find_one(
            (ConfigItem.group == "smtp") & (ConfigItem.key == key)
        )
        if item:
            item.value = value
            item.name = name
            item.updated_at = utc_now()
            await item.save()
        else:
            await ConfigItem(
                key=key,
                name=name,
                value=value,
                group="smtp",
                description="SMTP 配置",
                updated_at=utc_now(),
            ).insert()
