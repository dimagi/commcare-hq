from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
import django.core.exceptions
from django.template.response import TemplateResponse
from django.utils.deprecation import MiddlewareMixin

from corehq import toggles
from corehq.apps.domain.auth import (
    API_KEY,
    BASIC,
    DIGEST,
    determine_authtype_from_header,
    get_username_and_password_from_request,
)
from corehq.apps.users.models import CouchUser, InvalidUser, AnonymousCouchUser
from corehq.apps.users.util import username_to_user_id
from corehq.toggles import PUBLISH_CUSTOM_REPORTS

SESSION_USER_KEY_PREFIX = "session_user_doc_%s"


def is_public_reports(view_kwargs, request):
    return (
        request.user.is_anonymous and
        'domain' in view_kwargs and
        request.path.startswith('/a/{}/reports/custom'.format(view_kwargs['domain'])) and
        PUBLISH_CUSTOM_REPORTS.enabled(view_kwargs['domain'])
    )


class UsersMiddleware(MiddlewareMixin):

    def __init__(self, get_response=None):
        super(UsersMiddleware, self).__init__(get_response)
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
        request.analytics_enabled = True
        if 'domain' in view_kwargs:
            request.domain = view_kwargs['domain']
        if 'org' in view_kwargs:
            request.org = view_kwargs['org']
        auth_type = determine_authtype_from_header(request, default='NONE')
        if auth_type in (BASIC, DIGEST, API_KEY) and 'domain' in view_kwargs:
            # User is not yet authenticated, but setting request.domain (above) and request.couch_user will allow
            # us to check location-based permissions before we can check authentication.
            # See LocationAccessMiddleware.process_view()
            username, _ = get_username_and_password_from_request(request)
            request.couch_user = CouchUser.get_by_username(username) or InvalidUser()
        if request.user and request.user.is_authenticated:
            user_id = username_to_user_id(request.user.username)
            request.couch_user = CouchUser.get_by_user_id(user_id)
            if not request.couch_user.analytics_enabled:
                request.analytics_enabled = False
            if 'domain' in view_kwargs:
                domain = request.domain
                if not request.couch_user:
                    request.couch_user = InvalidUser()
                if request.couch_user:
                    request.couch_user.current_domain = domain
        elif is_public_reports(view_kwargs, request):
            request.couch_user = AnonymousCouchUser()
        return None
