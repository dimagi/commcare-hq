from django.conf import settings
import django.core.exceptions

from corehq.apps.domain.models import Domain

_SESSION_KEY_SELECTED_DOMAIN = '_domain_selected_domain'

############################################################################################################

class DomainMiddleware(object):
    def __init__(self):        
        # Normally we'd expect this class to be pulled out of the middleware list, too,
        # but in case someone forgets, this will stop this class from being used.
        found_domain_app = False
        for app_name in settings.INSTALLED_APPS:
            if app_name == "domain" or app_name.endswith(".domain"):
                found_domain_app = True
                break
        if not found_domain_app:
            raise django.core.exceptions.MiddlewareNotUsed

    # Always put a user's active domains in request.user object
    # Only fill in a non-null selected_domain for clearly-correct cases: session's domain is
    # in active set, or there's no domain in the session and only one possible domain in the
    # active set.
    #
    # Otherwise, selected_domain is None, and the login_and_domain_requested decorator will
    # catch it and send the user to the appropriate redirect.
    
    # Unclear whether we want this on process_request or process_view - they seem to be called the same
    # number of times, so it's likely a matter of whether we want the absence/presence of a good domain
    # to stop processing. As far as I can tell right now, with our current use cases the choice doesn't 
    # matter.
    
    #def process_request(self, request):
    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        # Lookup is done via the ContentTypes framework, stored in the domain_membership table
        # id(user) == id(request.user), so we can save a lookup into request by using 'user' alone    
        active_domains = Domain.active_for_user(user)
        user.active_domains = active_domains
        user.selected_domain = None # default case
        domain_from_session = request.session.get(_SESSION_KEY_SELECTED_DOMAIN, None)
        
        if domain_from_session and domain_from_session in active_domains:
            user.selected_domain = domain_from_session

        if not domain_from_session and len(active_domains) == 1:
            request.session[_SESSION_KEY_SELECTED_DOMAIN] = active_domains[0]
            user.selected_domain = active_domains[0]

        return None
    
############################################################################################################
