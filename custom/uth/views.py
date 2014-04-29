from corehq.apps.domain.decorators import login_or_digest
from django.views.decorators.http import require_POST
import json
from django.http import HttpResponse
from custom.uth.utils import match_case


@require_POST
@login_or_digest
def vscan_upload(request, domain, **kwargs):
    scanner_serial = request.POST.get('scanner_serial', None)
    scan_id = request.POST.get('scan_id', None)
    date = request.POST.get('date', None)

    if not (scanner_serial and scan_id and date):
        response_data = {}
        response_data['result'] = 'failed'
        response_data['message'] = 'Missing required parameters'
    else:
        case = match_case(scanner_serial, scan_id, date)
        # attach_images_to_case(case, [])

        response_data = {}
        response_data['result'] = 'success'
        response_data['message'] = ''

    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_POST
@login_or_digest
def sonosite_upload(request, domain, **kwargs):
    response_data = {}
    response_data['result'] = 'success'
    response_data['message'] = ''

    return HttpResponse(json.dumps(response_data), content_type="application/json")
