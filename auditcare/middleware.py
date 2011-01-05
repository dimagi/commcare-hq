from django.conf import settings
import django.core.exceptions
import logging
from auditcare.models import AuditEvent

class AuditMiddleware(object):
    def __init__(self):
        self.active = False
        self.log_admin = True
        
        if hasattr(settings, "AUDIT_ADMIN_VIEWS"):
            self.log_admin=settings.AUDIT_ADMIN_VIEWS
        else:
            logging.info("You do not have AUDIT_ADMIN_VIEWS settings variable setup, by default logging all admin view access")
                    
        if not hasattr(settings, "AUDIT_VIEWS"):
            logging.warning("You do not have the AUDIT_VIEWS settings variable setup.  If you want to setup central view call audit events, please add the property and populate it with fully qualified view names.")
            self.active=False
        else:
            self.active=True


    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Simple centralized manner to audit views without having to modify the requisite code.  This is an alternate
        way to manage audit events rather than using the decorator.
        """

        if hasattr(view_func, 'func_name'): #is this just a plain jane __builtin__.function
            fqview = "%s.%s" % (view_func.__module__, view_func.func_name)
        else:
            #just assess it from the classname for the class based view
            fqview = "%s.%s" % (view_func.__module__, view_func.__class__.__name__)
        if (fqview.startswith('django.contrib.admin') or fqview.startswith('reversion.admin')) and self.log_admin:
            AuditEvent.objects.audit_view(request, request.user, view_func)
        else:
            if self.active:
                user = request.user
                if settings.AUDIT_VIEWS.__contains__(fqview):
                    AuditEvent.objects.audit_view(request, request.user, view_func)
        return None

