from corehq.apps.domain.decorators import login_or_digest
from django.views.decorators.http import require_POST
import json
from django.http import HttpResponse
from custom.uth.utils import match_case, get_case_id, get_study_id
import zipfile
from custom.uth.models import SonositeUpload


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

    zip_file = zipfile.ZipFile(request.FILES['file'])

    # find patient config
    try:
        config = [f for f in zip_file.namelist() if 'PT_PPS.XML' in f][0]
    except Exception as e:
        response_data['result'] = 'failed'
        response_data['message'] = 'Could not load config file: %s' % (e.message)
        return HttpResponse(json.dumps(response_data), content_type="application/json")

    case_id = get_case_id(zip_file.read(config))
    study_id = get_study_id(zip_file.read(config))

    upload = SonositeUpload(
        domain=domain,
        study_id=study_id,
        related_case_id=case_id,
    )
    upload.save()

    # parsing the zip messes with file pointer, so reset
    # before trying to save
    zip_file.fp.seek(0)
    upload.put_attachment(
        zip_file.fp,
        'upload.zip',
        'application/zip'
    )

    # TODO create subcase with images for it here

    response_data['result'] = 'uploaded'
    response_data['message'] = 'uploaded'
    return HttpResponse(json.dumps(response_data), content_type="application/json")
