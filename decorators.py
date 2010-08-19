from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse,Http404
from ashandapp.models import CareTeam
import logging

def log_access(view_func):
    """
    Decorator for view - log each url and all params you're looking at.
    """
    def _log_access(request, *args, **kwargs):
        print args
        print kwargs
        print request.path
        print request.GET
        print view_func.__code__        
        print view_func.func_name
        print request.user
        print request.is_caregiver
        print request.is_provider
        print request.is_patient
        ret = view_func(request, * args, **kwargs)        
        return ret
    return _log_access



