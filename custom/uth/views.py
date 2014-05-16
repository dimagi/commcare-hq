from corehq.apps.domain.decorators import login_or_digest
from django.views.decorators.http import require_POST, require_GET
import json
from django.http import HttpResponse, Http404
from custom.uth.utils import (
    get_case_id,
    get_study_id,
    put_request_files_in_doc,
)
from custom.uth.models import SonositeUpload, VscanUpload
from custom.uth.tasks import async_create_case, async_find_and_attach
from dimagi.utils.couch.database import get_db
from custom.uth.const import UTH_DOMAIN


@require_POST
@login_or_digest
def vscan_upload(request, domain, **kwargs):
    if domain != UTH_DOMAIN:
        raise Http404()

    scanner_serial = request.POST.get('scanner_serial', None)
    scan_id = request.POST.get('scan_id', None)

    if not (scanner_serial and scan_id):
        response_data = {}
        response_data['result'] = 'failed'
        response_data['message'] = 'Missing required parameters'
    else:
        upload = VscanUpload(
            scanner_serial=scanner_serial,
            scan_id=scan_id,
        )
        upload.save()

        put_request_files_in_doc(request, upload)

        async_find_and_attach.delay(upload._id)

        response_data = {}
        response_data['result'] = 'success'
        response_data['message'] = ''

    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_GET
@login_or_digest
def pending_exams(request, domain, scanner_serial, **kwargs):
    if domain != UTH_DOMAIN:
        raise Http404()

    if not scanner_serial:
        response_data = {}
        response_data['result'] = 'failed'
        response_data['message'] = 'Missing scanner serial'
        return HttpResponse(json.dumps(response_data), content_type="application/json")

    results = get_db().view(
        'uth/uth_lookup',
        startkey=[UTH_DOMAIN, scanner_serial],
        endkey=[UTH_DOMAIN, scanner_serial, {}],
    ).all()

    exam_ids = [r['key'][-1] for r in results]

    response_data = {}
    response_data['result'] = 'success'
    response_data['exam_ids'] = exam_ids
    return HttpResponse(json.dumps(response_data), content_type="application/json")


@require_POST
@login_or_digest
def sonosite_upload(request, domain, **kwargs):
    if domain != UTH_DOMAIN:
        raise Http404()

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

    put_request_files_in_doc(request, upload)

    async_create_case.delay(upload._id)

    response_data['result'] = 'uploaded'
    response_data['message'] = 'uploaded'
    return HttpResponse(json.dumps(response_data), content_type="application/json")
