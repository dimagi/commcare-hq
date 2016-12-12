from django.http import HttpResponseNotFound, HttpResponseForbidden, \
    StreamingHttpResponse
from corehq.apps.case_importer.tracking.dbaccessors import get_case_uploads
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.tracking.permissions import user_may_view_file_upload
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.users.dbaccessors.couch_users import get_display_name_for_user_id
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_request
from corehq.util.view_utils import set_file_download
from dimagi.utils.web import json_response
from soil.progress import get_task_status
from soil.util import get_task


@require_can_edit_data
def case_uploads(request, domain):
    try:
        limit = int(request.GET.get('limit'))
    except (TypeError, ValueError):
        limit = 10

    def to_user_json(case_upload):
        tz = get_timezone_for_request()
        task_status = get_task_status(get_task(case_upload.task_id))
        return {
            'created': ServerTime(case_upload.created).user_time(tz).ui_string(),
            'domain': case_upload.domain,
            'upload_id': case_upload.upload_id,
            'task_status': {
                'state': task_status.state,
                'progress': {
                    'percent': task_status.progress.percent,
                },
                'result': task_status.result
            },
            'user': get_display_name_for_user_id(
                domain, case_upload.couch_user_id, default=''),
            'case_type': case_upload.case_type,
            'upload_file_name': case_upload.upload_file_name,
            'upload_file_length': case_upload.upload_file_length,
            'upload_file_download_allowed': user_may_view_file_upload(
                domain, request.couch_user, case_upload)
        }

    case_uploads = [to_user_json(case_upload)
                    for case_upload in get_case_uploads(domain, limit)]
    return json_response(case_uploads)


@require_can_edit_data
def case_upload_file(request, domain, upload_id):
    try:
        case_upload = CaseUploadRecord.objects.get(upload_id=upload_id, domain=domain)
    except CaseUploadRecord.DoesNotExist:
        return HttpResponseNotFound()

    if not user_may_view_file_upload(domain, request.couch_user, case_upload):
        return HttpResponseForbidden()

    response = StreamingHttpResponse(open(case_upload.get_tempfile(), 'rb'))

    set_file_download(response, case_upload.upload_file_meta.filename)
    return response
