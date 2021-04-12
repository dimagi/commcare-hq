#modified version of django-axes axes/decorator.py
#for more information see: http://code.google.com/p/django-axes/
from argparse import ArgumentTypeError

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest

from .utils.export import write_export_from_all_log_events

from corehq.util.argparse_types import date_type


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
