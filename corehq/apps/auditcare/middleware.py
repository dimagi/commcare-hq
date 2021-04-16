import logging
from types import FunctionType

from django.conf import settings

from .models import NavigationEventAudit

log = logging.getLogger(__name__)


class AuditMiddleware:

    def __init__(self, get_response):
        """
        Audit middleware needs to be enabled on site after the login/user info
        is instantiated on the request object.

        Auditing is controlled by three settings:
        - AUDIT_ALL_VIEWS: When true other settings are ignored.
        - AUDIT_VIEWS: List of fully qualified view names to audit.
        - AUDIT_MODULES: List of fully qualified module names to audit.
        - AUDIT_ADMIN_VIEWS: Audit admin views in `django.contrib.admin`
            and `reversion.admin` modules
        """
        self.get_response = get_response
        self.active = any(getattr(settings, name, False) for name in [
            "AUDIT_ALL_VIEWS", "AUDIT_VIEWS", "AUDIT_MODULES", "AUDIT_ADMIN_VIEWS"
        ])
        self.audit_modules = tuple(settings.AUDIT_MODULES)
        self.audit_views = set(settings.AUDIT_VIEWS)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Simple centralized manner to audit views without having to modify the
        requisite code.  This is an alternate way to manage audit events rather
        than using the decorator.
        """
        if self.active and self.should_audit(view_func):
            audit_doc = NavigationEventAudit.audit_view(request, request.user, view_func, view_kwargs)
            if audit_doc:
                request.audit_doc = audit_doc
        return None

    def __call__(self, request):
        response = None
        try:
            response = self.get_response(request)
        finally:
            self._save_audit(request, response)
        return response

    def should_audit(self, view_func):
        fn = view_func if isinstance(view_func, FunctionType) else view_func.__class__
        view_name = f"{view_func.__module__}.{fn.__name__}"
        if (view_name == "django.contrib.staticfiles.views.serve"
                or view_name == "debug_toolbar.views.debug_media"):
            return False
        return (
            getattr(settings, 'AUDIT_ALL_VIEWS', False)
            or view_name in self.audit_views
            or view_name.startswith(self.audit_modules)
            or (
                getattr(settings, "AUDIT_ADMIN_VIEWS", True)
                and view_name.startswith(('django.contrib.admin', 'reversion.admin'))
            )
        )

    def _save_audit(self, request, response):
        """
        Save the audit document set in the request object.

        For auditing views, we need to verify on the response whether or not the
        permission was granted, we infer this from the status code. We also need
        to add the user field when it was not initially inferred from the
        sessionid, such as when using Api Key, Basic Auth, Digest Auth, or HMAC
        auth.
        """
        audit_doc = getattr(request, 'audit_doc', None)
        if audit_doc:
            if not audit_doc.user:
                if hasattr(request, 'audit_user'):
                    audit_doc.user = request.audit_user
                elif hasattr(request, 'couch_user'):
                    audit_doc.user = request.couch_user.username
            if response is not None:
                audit_doc.status_code = response.status_code
            try:
                audit_doc.save()
            except Exception:
                log.exception("error saving view audit")
