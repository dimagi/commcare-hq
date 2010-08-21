from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse,Http404
import logging

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



