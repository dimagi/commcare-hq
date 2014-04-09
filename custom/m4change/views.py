from django.views.decorators.http import require_POST
from custom.m4change.models import McctStatus
from django.core.files.base import ContentFile
from django.http.response import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import login_and_domain_required
from couchexport.export import Format
from corehq.apps.reports.views import require_case_view_permission
from dimagi.utils.couch.cache.cache_core import get_redis_client


@require_POST
def update_service_status(request, domain):
    forms = request.POST
    for lists in forms.lists():
        for list in lists:
            if list is None or len(list) < 2:
                continue
            form_id = list[0]
            new_status = list[1] if list[1].__len__() is not 1 else None
            reject_reason = list[2] if new_status == 'rejected' else None
            if new_status is not None:
                try:
                    mcct_status = McctStatus.objects.get(form_id=form_id, domain=domain)
                except McctStatus.DoesNotExist:
                    mcct_status = None
                if not mcct_status:
                    mcct_status = McctStatus(form_id=form_id, domain=domain, status=new_status)
                mcct_status.update_status(new_status, reject_reason)
    return HttpResponse(status=200)


@require_case_view_permission
@login_and_domain_required
@require_GET
def m4change_export_report(request, domain, export_hash):
    cache = get_redis_client()

    if cache.exists(export_hash):
        with open(cache.get(export_hash), 'r') as content_file:
            content = content_file.read()

        file = ContentFile(content)
        response = HttpResponse(file,'application/vnd.ms-excel')
        response['Content-Length'] = file.size
        response['Content-Disposition'] = 'attachment; filename="{filename}.{extension}"'.format(
                filename=export_hash,
                extension=Format.XLS
        )
        return response
    else:
        return HttpResponseNotFound("Bad request, or response not found.")
