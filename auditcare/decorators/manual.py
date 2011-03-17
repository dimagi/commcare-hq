from django.contrib.auth import authenticate
from django.contrib.auth.views import login as django_login, logout as django_logout

from models import AuditEvent

def log_access(view_func):
    """
    Decorator for view - log each url and all params you're looking at.
    """
    def _log_access(request, *args, **kwargs):
        AuditEvent.objects.audit_view(request, request.user, view_func)         
        ret = view_func(request, * args, **kwargs)        
        return ret
    return _log_access
