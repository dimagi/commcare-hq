from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    #user_login_failed,
)

from .utils import to_django_header


class AuditcareConfig(AppConfig):
    """Configure auditcare

    If `settings.AUDIT_TRACE_ID_HEADER` is set the request header it
    names will be saved with audit records. The value of this setting
    should be something like `"X-Amzn-Trace-Id"`.
    """
    name = __name__

    def ready(self):
        from .models import audit_login, audit_logout
        user_logged_in.connect(audit_login)
        user_logged_out.connect(audit_logout)
        #user_login_failed.connect(audit_login_failed)  FIXME
        install_trace_id_header()


def install_trace_id_header():
    from .models import AccessAudit, STANDARD_HEADER_KEYS
    trace_id_header = getattr(settings, "AUDIT_TRACE_ID_HEADER", None)
    if trace_id_header:
        assert isinstance(trace_id_header, str), \
            f"bad value: settings.AUDIT_TRACE_ID_HEADER={trace_id_header!r}"
        trace_id_header = to_django_header(trace_id_header)
        AccessAudit.trace_id_header = trace_id_header
        STANDARD_HEADER_KEYS.append(trace_id_header)
