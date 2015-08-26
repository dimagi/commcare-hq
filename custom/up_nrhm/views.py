import json
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from custom.up_nrhm.sql_data import ASHAAFChecklistData
from dimagi.utils.dates import force_to_datetime


@require_GET
def asha_af_report(request, domain):
    report = ASHAAFChecklistData(
        config=dict(
            doc_id=request.GET.get('doc_id'),
            date=force_to_datetime(request.GET.get('date')),
            domain=domain
        )
    )
    return HttpResponse(
        json.dumps(report.rows),
        content_type='application/json'
    )
