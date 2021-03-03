#modified version of django-axes axes/decorator.py
#for more information see: http://code.google.com/p/django-axes/
import logging
from argparse import ArgumentTypeError

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .decorators.login import lockout_response, log_request
from .models import AccessAudit, ACCESS_LOGOUT
from .utils import login_template
from .utils.export import write_export_from_all_log_events

from corehq.util.argparse_types import date_type

LOCKOUT_TEMPLATE = getattr(settings, 'AXES_LOCKOUT_TEMPLATE', None)
LOCKOUT_URL = getattr(settings, 'AXES_LOCKOUT_URL', None)
VERBOSE = getattr(settings, 'AXES_VERBOSE', True)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def export_all(request):
    try:
        start = date_type(request.GET.get('start'))
        end = date_type(request.GET.get('end'))
    except ArgumentTypeError as e:
        if 'start' in locals():
            return HttpResponseBadRequest(f'[end] {e}')
        else:
            return HttpResponseBadRequest(f'[start] {e}')

    response = HttpResponse()
    response['Content-Disposition'] = 'attachment; filename="AuditAll.csv"'
    write_export_from_all_log_events(response, start=start, end=end)
    return response


@csrf_protect
@never_cache
def audited_login(request, *args, **kwargs):
    kwargs['template_name'] = login_template()
    # call the login function
    response = LoginView.as_view(*args, **kwargs)(request)
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
            # failed, and lockout
            return lockout_response(request)
    return response


@login_required
@user_passes_test(lambda u: u.is_superuser)
def audited_views(request, *args, **kwargs):
    db = AccessAudit.get_db()
    views = db.view('auditcare/urlpath_by_user_date', reduce=False).all()
    template = "auditcare/audit_views.html"
    context = {"audit_views": views}
    return render(request, template, context)


def audited_logout(request, *args, **kwargs):
    # share some useful information
    logging.info("Logged logout for user %s" % (request.user.username))
    user = request.user
    # it's a successful login.
    ip = request.META.get('REMOTE_ADDR', '')
    ua = request.META.get('HTTP_USER_AGENT', '<unknown>')
    attempt = AccessAudit()
    attempt.doc_type = AccessAudit.__name__
    attempt.access_type = ACCESS_LOGOUT
    attempt.user_agent = ua
    attempt.user = user.username
    attempt.session_key = request.session.session_key
    attempt.ip_address = ip
    attempt.get_data = []
    attempt.post_data = []
    attempt.http_accept = request.META.get('HTTP_ACCEPT', '<unknown>')
    attempt.path_info = request.META.get('PATH_INFO', '<unknown>')
    attempt.failures_since_start = 0
    attempt.save()

    # call the logout function
    response = LogoutView.as_view(*args, **kwargs)(request)
    return response
