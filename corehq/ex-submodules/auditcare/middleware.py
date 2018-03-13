from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import traceback

from django.conf import settings
from django.contrib import admin
from django.utils.deprecation import MiddlewareMixin

from auditcare.models import AuditEvent
from auditcare.decorators import watch_login
from auditcare.decorators import watch_logout
from six.moves import filter

log = logging.getLogger(__name__)


class AuditMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        """
        Audit middleware needs to be enabled on site after the login/user info is instantiated on the request object.
        """
        super(AuditMiddleware, self).__init__(get_response)
        self.active = False
        self.log_admin = True
        
        if hasattr(settings, "AUDIT_ADMIN_VIEWS"):
            self.log_admin=settings.AUDIT_ADMIN_VIEWS

        if not getattr(settings, 'AUDIT_ALL_VIEWS', False):
            if not hasattr(settings, "AUDIT_VIEWS"):
                log.warning("You do not have the AUDIT_VIEWS settings variable setup.  If you want to setup central view call audit events, please add the property and populate it with fully qualified view names.")
            elif not hasattr(settings, "AUDIT_MODULES"):
                log.warning("You do not have the AUDIT_MODULES settings variable setup.  If you want to setup central module audit events, please add the property and populate it with module names.")

            if hasattr(settings, "AUDIT_VIEWS") or hasattr(settings, "AUDIT_MODULES"):
                self.active = True
            else:
                self.active = False
        else:
            self.active = True


        #from django-axes
        #http://code.google.com/p/django-axes/source/browse/axes/middleware.py
        # watch the admin login page
        # and the regular auth login page


        #import traceback
        #log.error(traceback.print_stack())
        #and monitor logouts
        traces = traceback.format_stack(limit=5)
        def is_test_trace(item):
            if item.find('/django/test/') > 0:
                return True
            if item.find('/django/contrib/auth/tests/') > 0:
                return True
            return False
        is_tests = list(filter(is_test_trace, traces))
        if len(is_tests)  == 0:
            log.debug("Middleware is running in a running context")
            admin.site.login = watch_login(admin.site.login)
            admin.site.logout = watch_logout(admin.site.logout)
        else:
            log.debug("Middleware is running in a test context, disabling monkeypatch")


    @staticmethod
    def do_process_view(request, view_func, view_args, view_kwargs, extra={}):
        if (getattr(settings, 'AUDIT_MODULES', False) or
                getattr(settings, 'AUDIT_ALL_VIEWS', False) or
                getattr(settings, "AUDIT_VIEWS", False)):

            if hasattr(view_func, 'func_name'): #is this just a plain jane __builtin__.function
                fqview = "%s.%s" % (view_func.__module__, view_func.__name__)
            else:
                #just assess it from the classname for the class based view
                fqview = "%s.%s" % (view_func.__module__, view_func.__class__.__name__)
            if fqview == "django.contrib.staticfiles.views.serve" or fqview == "debug_toolbar.views.debug_media":
                return None

            def check_modules(view, audit_modules):
                return any((view.startswith(m) for m in audit_modules))

            audit_doc = None

            if (fqview.startswith('django.contrib.admin') or fqview.startswith('reversion.admin')) and getattr(settings, "AUDIT_ADMIN_VIEWS", True):
                audit_doc = AuditEvent.audit_view(request, request.user, view_func, view_kwargs)
            elif (check_modules(fqview, settings.AUDIT_MODULES) or
                  fqview in settings.AUDIT_VIEWS or
                  getattr(settings, 'AUDIT_ALL_VIEWS', False)):
                audit_doc = AuditEvent.audit_view(request, request.user, view_func, view_kwargs, extra=extra)
            if audit_doc:
                setattr(request, 'audit_doc', audit_doc)
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Simple centralized manner to audit views without having to modify the requisite code.  This is an alternate
        way to manage audit events rather than using the decorator.
        """
        resp = AuditMiddleware.do_process_view(request, view_func, view_args, view_kwargs)
        return None

    def process_response(self, request, response):
        """
        For auditing views, we need to verify on the response whether or not the permission was granted, we infer this from the status code.
        Update the audit document set in the request object.
        """
        audit_doc = getattr(request, 'audit_doc', None)
        if audit_doc:
            audit_doc.status_code = response.status_code
            audit_doc.save()
        return response

