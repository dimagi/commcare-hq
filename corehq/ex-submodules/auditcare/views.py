#modified version of django-axes axes/decorator.py
#for more information see: http://code.google.com/p/django-axes/
from __future__ import absolute_import
from __future__ import unicode_literals
import csv342 as csv
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from auditcare.utils import login_template
from auditcare.decorators.login import lockout_response
from auditcare.decorators.login import log_request
from auditcare.inspect import history_for_doc

from django.conf import settings
from django.shortcuts import render
from auditcare import models
from auditcare.models import AccessAudit

import logging


LOCKOUT_TEMPLATE = getattr(settings, 'AXES_LOCKOUT_TEMPLATE', None)
LOCKOUT_URL = getattr(settings, 'AXES_LOCKOUT_URL', None)
VERBOSE = getattr(settings, 'AXES_VERBOSE', True)


def export_all(request):
    auditEvents = AccessAudit.view("auditcare/by_date_access_events", descending=True, include_docs=True).all()
    response = HttpResponse()
    response['Content-Disposition'] = 'attachment; filename="AuditAll.csv"'
    writer = csv.writer(response)
    writer.writerow(['User', 'Access Type', 'Date'])
    for a in auditEvents:
        writer.writerow([a.user, a.access_type, a.event_date])
    return response

from django.contrib.auth import views as auth_views


@csrf_protect
@never_cache
def audited_login(request, *args, **kwargs):
    func = auth_views.login
    kwargs['template_name'] = login_template()
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
    func = auth_views.logout
    logging.info("Function: %s" %(func.__name__))
    logging.info("Logged logout for user %s" % (request.user.username))
    user = request.user
    # it's a successful login.
    ip = request.META.get('REMOTE_ADDR', '')
    ua = request.META.get('HTTP_USER_AGENT', '<unknown>')
    attempt = AccessAudit()
    attempt.doc_type=AccessAudit.__name__
    attempt.access_type = models.ACCESS_LOGOUT
    attempt.user_agent=ua
    attempt.user = user.username
    attempt.session_key = request.session.session_key
    attempt.ip_address=ip
    attempt.get_data=[]
    attempt.post_data=[]
    attempt.http_accept=request.META.get('HTTP_ACCEPT', '<unknown>')
    attempt.path_info=request.META.get('PATH_INFO', '<unknown>')
    attempt.failures_since_start=0
    attempt.save()

    # call the logout function
    response = func(request, *args, **kwargs)
    return response


@login_required()
@user_passes_test(lambda u: u.is_superuser)
def model_instance_history(request, model_name, model_uuid, *args, **kwargs):
    # it's for a particular model
    context = {}
    db = AccessAudit.get_db()

    if ContentType.objects.filter(name=model_name).count() == 0:
        # it's couchdbkit
        obj = db.get(model_uuid)
    else:
        obj = ContentType.objects.filter(name=model_name)[0].model_class().objects.get(id=model_uuid)

    context['change_history'] = history_for_doc(obj)
    context['model'] = model_name
    context['model_uuid'] = model_uuid
    return render(request, 'auditcare/model_instance_history.html', context)


@login_required()
@user_passes_test(lambda u: u.is_superuser)
def single_model_history(request, model_name, *args, **kwargs):
    # it's for a particular model
    context = {}
    db = AccessAudit.get_db()
    vals = db.view('auditcare/model_actions_by_id', group=True, startkey=[model_name, ''], endkey=[model_name, 'z']).all()
    model_dict= dict((x['key'][1], x['value']) for x in vals)
    context['instances_dict']=model_dict
    context['model'] = model_name
    return render(request, 'auditcare/single_model_changes.html', context)


@login_required()
@user_passes_test(lambda u: u.is_superuser)
def model_histories(request, *args, **kwargs):
    """
    Looks at all the audit model histories and shows for a given model
    """
    db = AccessAudit.get_db()
    vals = db.view('auditcare/model_actions_by_id', group=True, group_level=1).all()
    # do a dict comprehension here because we know all the keys in this reduce are unique
    model_dict = dict((x['value'][0], x['value']) for x in vals)
    context = {'model_dict': model_dict}
    return render(request, 'auditcare/model_changes.html', context)

