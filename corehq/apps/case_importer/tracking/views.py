from django.http import HttpResponseNotFound, HttpResponseForbidden, \
    StreamingHttpResponse

from corehq.apps.case_importer.tracking.dbaccessors import get_case_upload_records
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

    case_uploads = [case_upload_to_user_json(case_upload, request)
                    for case_upload in get_case_upload_records(domain, limit)]
    return json_response(case_uploads)


@require_can_edit_data
def case_upload_file(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    if not user_may_view_file_upload(domain, request.couch_user, case_upload):
        return HttpResponseForbidden()

    def streaming_content():
        tempfile = case_upload.get_tempfile()
        with open(tempfile, 'rb') as f:
            for chunk in f:
                yield chunk

    response = StreamingHttpResponse(streaming_content())

    set_file_download(response, case_upload.upload_file_meta.filename)
    return response
