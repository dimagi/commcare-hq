#modified version of django-axes axes/decorator.py
#for more information see: http://code.google.com/p/django-axes/
from auditcare.decorators.login import lockout_response
from auditcare.decorators.login import log_request

try:
    from functools import wraps
except ImportError:
    from django.utils.functional import wraps  # Python 2.4 fallback.

from django.conf import settings
from django.shortcuts import render_to_response
from django.template import RequestContext
from auditcare import models
from auditcare.models import AccessAudit, couchmodels
from auditcare.tables import AuditLogTable

import logging


LOCKOUT_TEMPLATE = getattr(settings, 'AXES_LOCKOUT_TEMPLATE', None)
LOCKOUT_URL = getattr(settings, 'AXES_LOCKOUT_URL', None)
VERBOSE = getattr(settings, 'AXES_VERBOSE', True)

def auditAll(request, template="auditcare/index.html"):
    auditEvents = couchmodels.AccessAudit.view("auditcare/by_date_access_events", descending=True, include_docs=True).all()
    realEvents = [{'user': a.user, 
                   'date': a.event_date, 
                   'class': a.doc_type, 
                   'access_type': a.access_type } for a in auditEvents]
    return render_to_response(template, 
                              {"audit_table": AuditLogTable(realEvents, request=request)}, 
                              context_instance=RequestContext(request))

from django.contrib.auth import views as auth_views

def audited_login(request, *args, **kwargs):
    func = auth_views.login
    kwargs['template_name'] = settings.LOGIN_TEMPLATE
    # call the login function
    response = func(request, *args, **kwargs)
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


def audited_logout (request, *args, **kwargs):
    # share some useful information
    func = auth_views.logout
    logging.info("Function: %s" %(func.__name__))
    logging.info("Logged logout for user %s" % (request.user.username))
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
    return response

