from django.conf import settings
import django.core.exceptions

############################################################################################################

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
        if request.user:
            request.couch_user = request.user.get_profile().get_couch_user()
        return None
    
############################################################################################################
