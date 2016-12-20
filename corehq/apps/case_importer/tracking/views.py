from django.db import transaction
from django.http import HttpResponseNotFound, HttpResponseForbidden, \
    StreamingHttpResponse

from corehq.apps.case_importer.tracking.dbaccessors import get_case_upload_records, \
    get_case_ids_for_case_upload, get_form_ids_for_case_upload
from corehq.apps.case_importer.tracking.jsmodels import case_upload_to_user_json
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.tracking.permissions import user_may_view_file_upload
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.util.view_utils import set_file_download
from dimagi.utils.web import json_response


@require_can_edit_data
def case_uploads(request, domain):
    try:
        limit = int(request.GET.get('limit'))
    except (TypeError, ValueError):
        limit = 10

    case_upload_records = get_case_upload_records(domain, limit)

    with transaction.atomic():
        for case_upload_record in case_upload_records:
            if case_upload_record.set_task_status_json_if_finished():
                case_upload_record.save()

    case_uploads_json = [case_upload_to_user_json(case_upload_record, request)
                         for case_upload_record in case_upload_records]

    return json_response(case_uploads_json)


@require_can_edit_data
def case_upload_file(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    if not user_may_view_file_upload(domain, request.couch_user, case_upload):
        return HttpResponseForbidden()

    response = StreamingHttpResponse(open(case_upload.get_tempfile_ref_for_upload_ref(), 'rb'))

    set_file_download(response, case_upload.upload_file_meta.filename)
    return response


@require_can_edit_data
def case_upload_form_ids(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    ids_stream = ('{}\n'.format(form_id)
                  for form_id in get_form_ids_for_case_upload(case_upload))

    return StreamingHttpResponse(ids_stream, content_type='text/plain')


@require_can_edit_data
def case_upload_case_ids(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    ids_stream = ('{}\n'.format(case_id)
                  for case_id in get_case_ids_for_case_upload(case_upload))

    return StreamingHttpResponse(ids_stream, content_type='text/plain')
