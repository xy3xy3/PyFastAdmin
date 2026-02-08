"""模型集合。"""

from .rbac import RbacPolicy
from .admin_user import AdminUser

__all__ = ["RbacPolicy", "AdminUser"]
