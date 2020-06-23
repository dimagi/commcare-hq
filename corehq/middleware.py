import functools
import logging
import mimetypes
import os
import datetime
import re
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.views import LogoutView
from django.utils.deprecation import MiddlewareMixin

from corehq.apps.domain.models import Domain
from corehq.apps.domain.utils import legacy_domain_re
from corehq.const import OPENROSA_DEFAULT_VERSION
from dimagi.utils.logging import notify_exception

from dimagi.utils.parsing import json_format_datetime, string_to_utc_datetime

try:
    import psutil
except ImportError:
    psutil = None


# this isn't OR specific, but we like it to be included
OPENROSA_ACCEPT_LANGUAGE = "HTTP_ACCEPT_LANGUAGE"
OPENROSA_VERSION_HEADER = "HTTP_X_OPENROSA_VERSION"
OPENROSA_DATE_HEADER = "HTTP_DATE"
OPENROSA_HEADERS = [OPENROSA_VERSION_HEADER, OPENROSA_DATE_HEADER, OPENROSA_ACCEPT_LANGUAGE]


class OpenRosaMiddleware(MiddlewareMixin):
    """
    Middleware to support OpenRosa request/response standards compliance
    https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest
    """

    def process_request(self, request):
        # if there's a date header specified add that to the request
        # as a first class property
        or_headers = {}
        for header in OPENROSA_HEADERS:
            if header in request.META:
                or_headers[header] = request.META[header]
        request.openrosa_headers = or_headers

    def process_response(self, request, response):
        response[OPENROSA_VERSION_HEADER] = OPENROSA_DEFAULT_VERSION
        return response


profile_logger = logging.getLogger('profile_middleware')


class MemoryUsageMiddleware(object):
    """
    Stolen and modified from http://stackoverflow.com/a/12254394/8207

    This is a pretty poor, blunt tool and is not recommended to be treated as definitive truth.
    """
    _psutil_installed = None

    def _check_psutil(self):
        if self._psutil_installed is None:
            if psutil is None:
                profile_logger.warning('Install dev-requirements (psutil) in order to use MemoryUsageMiddleware')
                self._psutil_installed = False
            else:
                self._psutil_installed = True
        return self._psutil_installed

    def process_request(self, request):
        if self._check_psutil():
            request._profile_memory = psutil.Process(os.getpid()).get_memory_info()

    def process_response(self, request, response):
        if self._check_psutil() and hasattr(request, '_profile_memory'):
            mem = psutil.Process(os.getpid()).get_memory_info()
            diff = (mem.rss - request._profile_memory.rss) // 1024
            profile_logger.info('{} memory usage {} KB'.format(request.path, diff))
        return response


class TimingMiddleware(object):

    def process_request(self, request):
        request._profile_starttime = datetime.datetime.utcnow()

    def process_response(self, request, response):
        if hasattr(request, '_profile_starttime'):
            duration = datetime.datetime.utcnow() - request._profile_starttime
            profile_logger.info('{} time {}'.format(request.path, duration), extra={'duration': duration})
        return response


class LogLongRequestMiddleware(MiddlewareMixin):

    def process_request(self, request):
        request._profile_starttime = datetime.datetime.utcnow()

    def process_response(self, request, response):
        if hasattr(request, '_profile_starttime'):
            duration = datetime.datetime.utcnow() - request._profile_starttime
            if duration > datetime.timedelta(minutes=10):
                notify_exception(request, "Request took a very long time.", details={
                    'duration': duration.total_seconds(),
                })
        return response


class TimeoutMiddleware(MiddlewareMixin):

    @classmethod
    def update_secure_session(cls, session, is_secure, user, domain=None, path=None):
        session['secure_session'] = is_secure
        timeout = cls._get_timeout(session, is_secure, user, domain)
        session['secure_session_timeout'] = timeout
        session.set_expiry(timeout * 60)
        session['session_expiry'] = json_format_datetime(session.get_expiry_date())
        session['last_path'] = path

    @classmethod
    def _get_timeout(cls, session, is_secure, user, domain=None):
        if not is_secure:
            return settings.INACTIVITY_TIMEOUT
        domains = cls._get_relevant_domains(user, domain)

        timeouts = list(map(Domain.secure_timeout, domains))
        timeouts = list(filter(None, timeouts))

        # Include timeout in current session, important for users who are not domain members
        # (e.g., superusers) who visited a secure domain and are now looking at a non-secure domain
        if hasattr(session, 'secure_session_timeout'):
            timeouts.append(session['secure_session_timeout'])

        return min(timeouts) if timeouts else settings.SECURE_TIMEOUT

    @classmethod
    def _get_relevant_domains(cls, couch_user, domain=None):
        domains = []

        # Include current domain, which user may not be a member of
        if domain:
            domains.append(domain)

        if not couch_user:
            return domains

        domains.extend(couch_user.get_domains())

        from corehq.apps.users.models import DomainPermissionsMirror
        for domain in domains:
            domains.extend(DomainPermissionsMirror.mirror_domains(domain))

        return domains

    @staticmethod
    def _session_expired(timeout, activity):
        if activity is None:
            return False

        time = datetime.datetime.utcnow()
        time_since_activity = time - string_to_utc_datetime(activity)
        return time_since_activity > datetime.timedelta(minutes=timeout)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return

        secure_session = request.session.get('secure_session')
        domain = getattr(request, "domain", None)
        domain_obj = Domain.get_by_name(domain) if domain else None
        if not domain:
            domain_obj = getattr(request, "project", None)

        # figure out if we want to switch to secure_sessions
        change_to_secure_session = (
            not secure_session
            and (
                (domain_obj and domain_obj.secure_sessions)
                or any(filter(Domain.is_secure_session_required,
                             self._get_relevant_domains(request.couch_user, domain)))
            )
        )

        secure_session = secure_session or change_to_secure_session
        timeout = self._get_timeout(request.session, secure_session, request.couch_user, domain)
        if change_to_secure_session:
            # force re-authentication if the user has been logged in longer than the secure timeout
            if self._session_expired(timeout, request.user.last_login):
                LogoutView.as_view(template_name=settings.BASE_TEMPLATE)(request)
                # this must be after logout so it is attached to the new session
                self.update_secure_session(request.session, True, request.couch_user, domain, request.path)
                return HttpResponseRedirect(reverse('login') + '?next=' + request.path)

            self.update_secure_session(request.session, True, request.couch_user, domain, request.path)

        if not getattr(request, '_bypass_sessions', False):
            self.update_secure_session(request.session, secure_session, request.couch_user, domain, request.path)


def always_allow_browser_caching(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        response = fn(*args, **kwargs)
        response._always_allow_browser_caching = True
        return response
    return inner


class NoCacheMiddleware(MiddlewareMixin):

    def process_response(self, request, response):
        if not self._explicitly_marked_safe(response):
            response['Cache-Control'] = "private, no-cache, no-store, must-revalidate, proxy-revalidate"
            response['Expires'] = "Thu, 01 Dec 1994 16:00:00 GMT"
            response['Pragma'] = "no-cache"
        else:
            max_age = getattr(response, '_cache_max_age', "31536000")
            content_type, _ = mimetypes.guess_type(request.path)
            response['Cache-Control'] = "max-age={}".format(max_age)
            del response['Vary']
            del response['Set-Cookie']
            response['Content-Type'] = content_type
            del response['Content-Language']
            response['Content-Length'] = len(response.content)
            del response['HTTP_X_OPENROSA_VERSION']
        return response

    @staticmethod
    def _explicitly_marked_safe(response):
        return getattr(response, '_always_allow_browser_caching', False)


class SentryContextMiddleware(MiddlewareMixin):
    """Add details to Sentry context.
    Should be placed after 'corehq.apps.users.middleware.UsersMiddleware'
    """
    def __init__(self, get_response=None):
        super(SentryContextMiddleware, self).__init__(get_response)
        try:
            from sentry_sdk import configure_scope
        except ImportError:
            raise MiddlewareNotUsed

        if not getattr(settings, 'SENTRY_CONFIGURED', None):
            raise MiddlewareNotUsed

    def process_view(self, request, view_func, view_args, view_kwargs):
        from sentry_sdk import configure_scope

        with configure_scope() as scope:
            if getattr(request, 'couch_user', None):
                scope.set_extra('couch_user_id', request.couch_user.get_id)
                scope.set_tag('user.username', request.couch_user.username)

            if getattr(request, 'domain', None):
                scope.set_tag('domain', request.domain)


class SelectiveSessionMiddleware(SessionMiddleware):

    def __init__(self, get_response=None):
        super().__init__(get_response)
        regexes = [
            '/favicon.ico$',
            '/ping_login/$',
            '/downloads/temp/ajax/',  # soil polling
            '/downloads/temp/heartbeat/',  # soil status
            '/a/{domain}/apps/view/[A-Za-z0-9-]+/current_version/$'  # app manager new changes polling
            '/hq/notifications/service/$',  # background request for notification (bell menu in top nav)
        ]
        if settings.BYPASS_SESSIONS_FOR_MOBILE:
            regexes.extend(getattr(settings, 'SESSION_BYPASS_URLS', []))
        self.bypass_re = [
            re.compile(regex.format(domain=legacy_domain_re)) for regex in regexes
        ]

    def _bypass_sessions(self, request):
        return any(rx.match(request.path_info) for rx in self.bypass_re)

    def process_request(self, request):
        super().process_request(request)
        if self._bypass_sessions(request):
            request.session.save = lambda *x: None
            request._bypass_sessions = True
