import StringIO
from django.core.files.base import ContentFile
from django.http.response import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import login_and_domain_required
from couchexport.export import Format
from corehq.apps.reports.views import require_case_view_permission
from dimagi.utils.couch.cache.cache_core import get_redis_client


@require_case_view_permission
@login_and_domain_required
@require_GET
def bihar_export_report(request, domain, export_hash):
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