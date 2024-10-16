from django.contrib.auth import logout
from django.utils.deprecation import MiddlewareMixin

from corehq.apps.users.models import CouchUser, InvalidUser
from corehq.apps.users.util import username_to_user_id

SESSION_USER_KEY_PREFIX = "session_user_doc_%s"


class UsersMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):
        request.analytics_enabled = True
        if 'domain' in view_kwargs:
            request.domain = view_kwargs['domain']
        if 'org' in view_kwargs:
            request.org = view_kwargs['org']
        if request.user and request.user.is_authenticated:
            if not request.user.is_active:
                logout(request)
                return self.get_response(request)
            user_id = username_to_user_id(request.user.username)
            couch_user = CouchUser.get_by_user_id(user_id)
            if not couch_user:
                couch_user = InvalidUser()
            request.couch_user = couch_user
            if not request.couch_user.analytics_enabled:
                request.analytics_enabled = False
            if 'domain' in view_kwargs:
                domain = request.domain
                request.couch_user.current_domain = domain
        return None
