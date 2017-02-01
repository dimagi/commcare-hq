from django.conf import settings
import django.core.exceptions
from corehq.apps.users.models import CouchUser, InvalidUser



SESSION_USER_KEY_PREFIX = "session_user_doc_%s"


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
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if 'domain' in view_kwargs:
            request.domain = view_kwargs['domain']
        if 'org' in view_kwargs:
            request.org = view_kwargs['org']
        if request.user.is_anonymous() and 'domain' in view_kwargs:
            request.couch_user = CouchUser.get_anonymous_mobile_worker(request.domain)
        if request.user and request.user.is_authenticated():
            request.couch_user = CouchUser.get_by_username(
                request.user.username, strict=False)
            if 'domain' in view_kwargs:
                domain = request.domain
                if not request.couch_user:
                    request.couch_user = InvalidUser()
                if request.couch_user:
                    request.couch_user.current_domain = domain
        return None
