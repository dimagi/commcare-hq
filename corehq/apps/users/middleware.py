from django.conf import settings
import django.core.exceptions

############################################################################################################
from corehq.apps.users.models import CouchUser

class UsersMiddleware(object):
    def __init__(self):        
        # Normally we'd expect this class to be pulled out of the middleware list, too,
        # but in case someone forgets, this will stop this class from being used.
        found_domain_app = False
        for app_name in settings.INSTALLED_APPS:
            if app_name == "users" or app_name.endswith(".users"):
                found_domain_app = True
                break
        if not found_domain_app:
            raise django.core.exceptions.MiddlewareNotUsed
    
    #def process_request(self, request):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user and hasattr(request.user, 'get_profile'):
            request.couch_user = CouchUser.from_django_user(request.user)
            if 'domain' in view_kwargs:
                request.couch_user.current_domain = view_kwargs['domain']
        return None
    
############################################################################################################
