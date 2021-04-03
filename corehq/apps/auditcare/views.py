#modified version of django-axes axes/decorator.py
#for more information see: http://code.google.com/p/django-axes/
from argparse import ArgumentTypeError

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render

from .models import AccessAudit
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


@login_required
@user_passes_test(lambda u: u.is_superuser)
def audited_views(request, *args, **kwargs):
    db = AccessAudit.get_db()
    views = db.view('auditcare/urlpath_by_user_date', reduce=False).all()
    template = "auditcare/audit_views.html"
    context = {"audit_views": views}
    return render(request, template, context)
