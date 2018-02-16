from __future__ import absolute_import
from django.conf import settings
import django.core.exceptions
from django.template.response import TemplateResponse
from django.utils.deprecation import MiddlewareMixin

from corehq import toggles
from corehq.apps.users.models import CouchUser, InvalidUser, AnonymousCouchUser
from corehq.apps.users.util import username_to_user_id
from corehq.toggles import ANONYMOUS_WEB_APPS_USAGE, PUBLISH_CUSTOM_REPORTS

SESSION_USER_KEY_PREFIX = "session_user_doc_%s"


def is_public_reports(view_kwargs, request):
    return (
        request.user.is_anonymous and
        'domain' in view_kwargs and
        request.path.startswith(u'/a/{}/reports/custom'.format(view_kwargs['domain'])) and
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
        if request.user.is_anonymous and 'domain' in view_kwargs:
            if ANONYMOUS_WEB_APPS_USAGE.enabled(view_kwargs['domain']):
                request.couch_user = CouchUser.get_anonymous_mobile_worker(request.domain)
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


class Enforce2FAMiddleware(MiddlewareMixin):
    """Require all superusers and staff accounts to have Two-Factor Auth enabled"""
    def __init__(self, get_response=None):
        super(Enforce2FAMiddleware, self).__init__(get_response)

        if settings.DEBUG:
            raise django.core.exceptions.MiddlewareNotUsed

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not (
            hasattr(request, 'user')
            and hasattr(request, 'couch_user')
            and request.user
            and request.couch_user
        ):
            return None

        if not toggles.TWO_FACTOR_SUPERUSER_ROLLOUT.enabled(request.user.username):
            return None
        elif not request.user.is_verified():
            if request.path.startswith('/account/') or request.couch_user.two_factor_disabled:
                return None
            else:
                return TemplateResponse(
                    request=request,
                    template='two_factor/core/otp_required.html',
                    status=403,
                )
