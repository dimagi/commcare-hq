from corehq.apps.domain.decorators import login_or_digest
from django.views.decorators.http import require_POST
import json
from django.http import HttpResponse
from custom.uth.utils import (
    get_case_id,
    get_study_id,
)
from custom.uth.models import SonositeUpload, VscanUpload
from custom.uth.tasks import async_create_case, async_find_and_attach


@require_POST
@login_or_digest
def vscan_upload(request, domain, **kwargs):
    scanner_serial = request.POST.get('scanner_serial', None)
    scan_id = request.POST.get('scan_id', None)
    # scan_time = request.POST.get('scan_time', None)

    if not (scanner_serial and scan_id): # and scan_time):
        response_data = {}
        response_data['result'] = 'failed'
        response_data['message'] = 'Missing required parameters'
    else:
        upload = VscanUpload(
            scanner_serial=scanner_serial,
            scan_id=scan_id,
        #    scan_time=scan_time
        )
        upload.save()

        for name, f in request.FILES.iteritems():
            upload.put_attachment(
                f,
                name,
            )

        # TODO delay
        async_find_and_attach(upload._id)

        response_data = {}
        response_data['result'] = 'success'
        response_data['message'] = ''

    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_POST
@login_or_digest
def sonosite_upload(request, domain, **kwargs):
    response_data = {}

    try:
        config_file = request.FILES.pop('PT_PPS.XML')[0].read()
    except Exception as e:
        response_data['result'] = 'failed'
        response_data['message'] = 'Could not load config file: %s' % (e.message)
        return HttpResponse(json.dumps(response_data), content_type="application/json")

    case_id = get_case_id(config_file)
    study_id = get_study_id(config_file)

    upload = SonositeUpload(
        study_id=study_id,
        related_case_id=case_id,
    )
    upload.save()

    for name, f in request.FILES.iteritems():
        upload.put_attachment(
            f,
            name,
        )

    # TODO delay
    async_create_case(upload._id)

    response_data['result'] = 'uploaded'
    response_data['message'] = 'uploaded'
    return HttpResponse(json.dumps(response_data), content_type="application/json")
