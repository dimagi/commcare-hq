from django.conf import settings
import django.core.exceptions

############################################################################################################
from corehq.apps.users.models import CouchUser, PublicUser, InvalidUser
from corehq.apps.domain.models import Domain

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
        if 'domain' in view_kwargs:
            request.domain = view_kwargs['domain']
        if request.user and hasattr(request.user, 'get_profile'):
            request.couch_user = CouchUser.from_django_user(request.user)
            if 'domain' in view_kwargs:
                domain = request.domain
                if not request.couch_user:
                    couch_domain = Domain.view("domain/domains",
                        key=domain,
                        reduce=False,
                        include_docs=True,
                        stale='update_after',
                    ).one()
                    if couch_domain and couch_domain.is_public:
                        request.couch_user = PublicUser(domain)
                    else:
                        request.couch_user = InvalidUser()
                if request.couch_user:
                    request.couch_user.current_domain = domain
        return None
    
############################################################################################################
