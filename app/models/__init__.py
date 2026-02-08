"""模型集合。"""

from .rbac_permission import RbacPermission
from .role import Role
from .admin_user import AdminUser
from .config_item import ConfigItem

__all__ = ["RbacPermission", "Role", "AdminUser", "ConfigItem"]
