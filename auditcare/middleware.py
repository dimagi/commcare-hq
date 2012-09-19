from __future__ import absolute_import
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
import logging
from auditcare.models import AuditEvent
from auditcare.decorators import watch_login
from auditcare.decorators import watch_logout
import traceback




class AuditMiddleware(object):
    def __init__(self):
        """
        Audit middleware needs to be enabled on site after the login/user info is instantiated on the request object.
        """
        self.active = False
        self.log_admin = True
        
        if hasattr(settings, "AUDIT_ADMIN_VIEWS"):
            self.log_admin=settings.AUDIT_ADMIN_VIEWS
        else:
            logging.info("You do not have AUDIT_ADMIN_VIEWS settings variable setup, by default logging all admin view access")

        if not getattr(settings, 'AUDIT_ALL_VIEWS', False):
            if not hasattr(settings, "AUDIT_VIEWS"):
                logging.warning("You do not have the AUDIT_VIEWS settings variable setup.  If you want to setup central view call audit events, please add the property and populate it with fully qualified view names.")
                self.active=False
            else:
                self.active=True
        else:
            self.active=True


        #from django-axes
        #http://code.google.com/p/django-axes/source/browse/axes/middleware.py
        # watch the admin login page
        # and the regular auth login page


        #import traceback
        #logging.error(traceback.print_stack())
        #and monitor logouts
        traces = traceback.format_stack(limit=5)
        def is_test_trace(item):
            if item.find('/django/test/') > 0:
                return True
            if item.find('/django/contrib/auth/tests/') > 0:
                return True
            return False
        is_tests = filter(is_test_trace, traces)
        if len(is_tests)  == 0:
            logging.debug("Middleware is running in a running context")
            admin.site.login = watch_login(admin.site.login)
            admin.site.logout = watch_logout(admin.site.logout)
        else:
            logging.debug("Middleware is running in a test context, disabling monkeypatch")


    @staticmethod
    def do_process_view(request, view_func, view_args, view_kwargs, extra={}):
        if getattr(settings, 'AUDIT_ALL_VIEWS', False) or getattr(settings, "AUDIT_VIEWS", False):
            if hasattr(view_func, 'func_name'): #is this just a plain jane __builtin__.function
                fqview = "%s.%s" % (view_func.__module__, view_func.func_name)
            else:
                #just assess it from the classname for the class based view
                fqview = "%s.%s" % (view_func.__module__, view_func.__class__.__name__)
            if fqview == "django.contrib.staticfiles.views.serve" or fqview == "debug_toolbar.views.debug_media":
                return None

            audit_doc = None
            if (fqview.startswith('django.contrib.admin') or fqview.startswith('reversion.admin')) and getattr(settings, "AUDIT_ADMIN_VIEWS", True):
                audit_doc = AuditEvent.audit_view(request, request.user, view_func, view_kwargs)
            else:
                user = request.user
                if settings.AUDIT_VIEWS.__contains__(fqview) or getattr(settings, 'AUDIT_ALL_VIEWS', False):
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

