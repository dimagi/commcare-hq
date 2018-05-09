from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq import privileges


reminders_framework_permission = lambda *args, **kwargs: (
    require_permission(Permissions.edit_data)(
        requires_privilege_with_fallback(privileges.REMINDERS_FRAMEWORK)(*args, **kwargs)
    )
)
