#modified version of django-axes axes/decorator.py
#for more information see: http://code.google.com/p/django-axes/
from __future__ import absolute_import
from __future__ import unicode_literals
import django
from django.contrib.auth.forms import AuthenticationForm

from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from auditcare import models
from auditcare.models import AccessAudit

# see if the user has overridden the failure limit
FAILURE_LIMIT = getattr(settings, 'AXES_LOGIN_FAILURE_LIMIT', 3)

# see if the user has set axes to lock out logins after failure limit
LOCK_OUT_AT_FAILURE = getattr(settings, 'AXES_LOCK_OUT_AT_FAILURE', True)

USE_USER_AGENT = getattr(settings, 'AXES_USE_USER_AGENT', False)

COOLOFF_TIME = getattr(settings, 'AXES_COOLOFF_TIME', 3)
if isinstance(COOLOFF_TIME, int):
    COOLOFF_TIME = timedelta(hours=COOLOFF_TIME)

import logging


LOCKOUT_TEMPLATE = getattr(settings, 'AXES_LOCKOUT_TEMPLATE', None)
LOCKOUT_URL = getattr(settings, 'AXES_LOCKOUT_URL', None)
VERBOSE = getattr(settings, 'AXES_VERBOSE', True)


def query2str(items):
    """Turns a dictionary into an easy-to-read list of key-value pairs.

    If there's a field called "password" it will be excluded from the output.
    """

    kvs = []
    for k, v in items:
        if k != 'password':
            kvs.append('%s=%s' % (k, v))

    return '\n'.join(kvs)

log = logging.getLogger(__name__)
if VERBOSE:
    log.info('AXES: BEGIN LOG')
    #log.info('Using django-axes ' + axes.get_version())


def get_user_attempt(request):
    """
    Returns access attempt record if it exists.
    Otherwise return None.
    """
    ip = request.META.get('REMOTE_ADDR', '')
    if USE_USER_AGENT:
        ua = request.META.get('HTTP_USER_AGENT', '<unknown>')

        attempts = AccessAudit.view('auditcare/login_events', key=['ip_ua', ip, ua], include_docs=True, limit=25).all()

        #attempts = AccessAttempt.objects.filter( user_agent=ua, ip_address=ip )
    else:
        attempts = AccessAudit.view('auditcare/login_events', key=['ip', ip], include_docs=True, limit=25).all()
        #attempts = AccessAttempt.objects.filter( ip_address=ip )

    attempts = sorted(attempts, key=lambda x: x.event_date, reverse=True)
    if not attempts:
        log.info("No attempts for given access, creating new attempt")
        return None

    #walk the attempts
    attempt = None
    for at in attempts:
        if at.access_type == models.ACCESS_FAILED:
            attempt = at
            break
        elif at.access_type == models.ACCESS_LOGIN:
            attempt = None
            break
        elif at.access_type == models.ACCESS_LOGOUT:
            attempt = None
            break



    if COOLOFF_TIME and attempt and datetime.utcnow() - attempt.event_date < COOLOFF_TIME:
        log.info("Last login failure is still within the cooloff time, incrementing last access attempt.")
    else:
        log.info("Last login failure is outside the cooloff time, creating new access attempt.")
        return None
    return attempt


def watch_logout(func):
    def decorated_logout (request, *args, **kwargs):
        # share some useful information
        if func.__name__ != 'decorated_logout' and VERBOSE:
            log.info('AXES: Calling decorated logout function: %s', func.__name__)
            if args: log.info('args: %s', args)
            if kwargs: log.info('kwargs: %s', kwargs)
        log.info("Function: %s", func.__name__)
        log.info("Logged logout for user %s", request.user.username)
        user = request.user
        #it's a successful login.
        ip = request.META.get('REMOTE_ADDR', '')
        ua = request.META.get('HTTP_USER_AGENT', '<unknown>')
        attempt = AccessAudit()
        attempt.doc_type=AccessAudit.__name__
        attempt.access_type = models.ACCESS_LOGOUT
        attempt.user_agent=ua
        attempt.user = user.username
        attempt.session_key = request.session.session_key
        attempt.ip_address=ip
        attempt.get_data=[] #[query2str(request.GET.items())]
        attempt.post_data=[]
        attempt.http_accept=request.META.get('HTTP_ACCEPT', '<unknown>')
        attempt.path_info=request.META.get('PATH_INFO', '<unknown>')
        attempt.failures_since_start=0
        attempt.save()

        # call the logout function
        response = func(request, *args, **kwargs)

        if func.__name__ == 'decorated_logout':
            # if we're dealing with this function itself, don't bother checking
            # for invalid login attempts.  I suppose there's a bunch of
            # recursion going on here that used to cause one failed login
            # attempt to generate 10+ failed access attempt records (with 3
            # failed attempts each supposedly)
            return response
        return response
    return decorated_logout




def watch_login(func):
    """
    Used to decorate the django.contrib.admin.site.login method.
    """


    def decorated_login(request, *args, **kwargs):
        # share some useful information
        if func.__name__ != 'decorated_login' and VERBOSE:
            log.info('AXES: Calling decorated function: %s', func.__name__)
            if args: log.info('args: %s', args)
            if kwargs: log.info('kwargs: %s', kwargs)

        # call the login function
        response = func(request, *args, **kwargs)

        if func.__name__ == 'decorated_login':
            # if we're dealing with this function itself, don't bother checking
            # for invalid login attempts.  I suppose there's a bunch of
            # recursion going on here that used to cause one failed login
            # attempt to generate 10+ failed access attempt records (with 3
            # failed attempts each supposedly)
            return response

        if request.method == 'POST':
            # see if the login was successful
            login_unsuccessful = (
                response and
                not response.has_header('location') and
                response.status_code != 302
            )
            if log_request(request, login_unsuccessful):
                return response
            else:
                #failed, and lockout
                return lockout_response(request)
        return response

    return decorated_login


def lockout_response(request):
    if LOCKOUT_TEMPLATE:
        context = RequestContext(request, {
            'cooloff_time': COOLOFF_TIME,
            'failure_limit': FAILURE_LIMIT,
        })
        return render_to_response(LOCKOUT_TEMPLATE, context)

    if LOCKOUT_URL:
        return HttpResponseRedirect(LOCKOUT_URL)

    if COOLOFF_TIME:
        return HttpResponse("Account locked: too many login attempts.  "
                            "Please try again later.")
    else:
        return HttpResponse("Account locked: too many login attempts.  "
                            "Contact an admin to unlock your account.")


def log_request(request, login_unsuccessful):
    failures = 0
    attempt = get_user_attempt(request)

    if attempt:
        failures = attempt.failures_since_start

    # no matter what, we want to lock them out
    # if they're past the number of attempts allowed
    if failures > FAILURE_LIMIT and LOCK_OUT_AT_FAILURE:
        # We log them out in case they actually managed to enter
        # the correct password.
        logout(request)
        log.warning('AXES: locked out %s after repeated login attempts.', attempt.ip_address)
        return False

    if login_unsuccessful:
        #interpret the auth form to get the user in question
        if request.method == "POST":
            form = AuthenticationForm(data=request.POST)
            if form.is_valid():
                attempted_username = form.get_user().username
            else:
                attempted_username = form.data.get('username')
                attempted_password = form.data.get('password')

        # add a failed attempt for this user
        failures += 1

        # Create an AccessAttempt record if the login wasn't successful
        # has already attempted, update the info
        if attempt:
            #attempt.get_data.append(query2str(request.GET.items()))
            #attempt.post_data.append(query2str(request.POST.items()))
            attempt.access_type = models.ACCESS_FAILED
            attempt.user = attempted_username
            attempt.http_accept = request.META.get('HTTP_ACCEPT', '<unknown>')
            attempt.path_info = request.META.get('PATH_INFO', '<unknown>')
            attempt.failures_since_start = failures
            attempt.event_date = datetime.utcnow() #why do we do this?
            attempt.save()
            log.info('AXES: Repeated login failure by %s. Updating access '
                     'record. Count = %s', attempt.ip_address, failures)
        else:
            ip = request.META.get('REMOTE_ADDR', '')
            ua = request.META.get('HTTP_USER_AGENT', '<unknown>')
            attempt = AccessAudit()
            attempt.event_date = datetime.utcnow()
            attempt.doc_type=AccessAudit.__name__
            attempt.access_type = models.ACCESS_FAILED
            attempt.user_agent=ua
            attempt.user = attempted_username
            attempt.ip_address=ip
            #attempt.get_data = [query2str(request.GET.items())]
            #attempt.post_data= [query2str(request.POST.items())]
            attempt.http_accept=request.META.get('HTTP_ACCEPT', '<unknown>')
            attempt.path_info=request.META.get('PATH_INFO', '<unknown>')
            attempt.failures_since_start=failures
            attempt.save()
            log.info('AXES: New login failure by %s. Creating access record.', ip)

    return True
