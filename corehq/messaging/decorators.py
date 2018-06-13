from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.toggles import NEW_REMINDERS_MIGRATOR
from corehq import privileges
from functools import wraps


def require_privilege_but_override_for_migrator(privilege):
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if (
                hasattr(request, 'couch_user') and
                NEW_REMINDERS_MIGRATOR.enabled(request.couch_user.username)
            ):
                return fn(request, *args, **kwargs)
            return requires_privilege_with_fallback(privilege)(fn)(request, *args, **kwargs)
        return wrapped
    return decorate


reminders_framework_permission = require_privilege_but_override_for_migrator(privileges.REMINDERS_FRAMEWORK)
