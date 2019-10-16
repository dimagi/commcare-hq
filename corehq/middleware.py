import functools
import logging
import mimetypes
import os
import datetime
import re
import traceback
from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.views import logout as django_logout
from django.utils.deprecation import MiddlewareMixin

from corehq import toggles
from corehq.apps.domain.models import Domain
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

    @staticmethod
    def _session_expired(timeout, activity, time):
        if activity is None:
            return False

        time_since_activity = time - string_to_utc_datetime(activity)
        return time_since_activity > datetime.timedelta(minutes=timeout)

    @staticmethod
    def _user_requires_secure_session(couch_user):
        return couch_user and any(Domain.is_secure_session_required(domain)
                                  for domain in couch_user.get_domains())

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return

        secure_session = request.session.get('secure_session')
        timeout = settings.SECURE_TIMEOUT if secure_session else settings.INACTIVITY_TIMEOUT
        domain = getattr(request, "domain", None)
        now = datetime.datetime.utcnow()

        # figure out if we want to switch to secure_sessions
        change_to_secure_session = (
            not secure_session
            and (
                (domain and Domain.is_secure_session_required(domain))
                or self._user_requires_secure_session(request.couch_user)))

        if change_to_secure_session:
            timeout = settings.SECURE_TIMEOUT
            # force re-authentication if the user has been logged in longer than the secure timeout
            if self._session_expired(timeout, request.user.last_login, now):
                django_logout(request, template_name=settings.BASE_TEMPLATE)
                # this must be after logout so it is attached to the new session
                request.session['secure_session'] = True
                request.session.set_expiry(timeout * 60)
                return HttpResponseRedirect(reverse('login') + '?next=' + request.path)

            request.session['secure_session'] = True

        request.session.set_expiry(timeout * 60)


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

            if getattr(request, 'domain', None):
                scope.set_tag('domain', request.domain)


session_logger = logging.getLogger('session_access_log')


def log_call(func):
    def with_logging(*args, **kwargs):
        session_logger.info("\n\n\n")
        session_logger.info(func.__name__ + " was called")
        session_logger.info("\n\n\n")
        for line in traceback.format_stack():
            white_list = ['corehq/', 'custom/', func.__name__]
            if any([c in line for c in white_list]):
                session_logger.info(line.strip())
        return func(*args, **kwargs)
    return with_logging


def decorate_all_methods(decorator):
    def decorate(cls):
        for attr in dir(cls):
            if "__" not in attr and callable(getattr(cls, attr)):
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls
    return decorate


@decorate_all_methods(log_call)
class LoggingSessionStore(SessionStore):
    pass


class LoggingSessionMiddleware(SessionMiddleware):

    def process_request(self, request):
        try:
            match = re.search(r'/a/[0-9a-z-]+', request.path)
            if match:
                domain = match.group(0).split('/')[-1]
                if toggles.SESSION_MIDDLEWARE_LOGGING.enabled(domain):
                    self.SessionStore = LoggingSessionStore
                else:
                    self.SessionStore = SessionStore
        except Exception as e:
            session_logger.error(
                "Exception {} in LoggingSessionMiddleware for url {}".format(
                    str(e), request.path)
            )
            pass
        super().process_request(request)
