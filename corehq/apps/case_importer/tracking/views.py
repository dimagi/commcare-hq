from corehq.apps.case_importer.tracking.dbaccessors import get_case_uploads
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_request
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
        case_upload_json = case_upload.to_json()
        tz = get_timezone_for_request()
        task_status = get_task_status(get_task(case_upload_json['task_id']))
        return {
            'created': ServerTime(case_upload.created).user_time(tz).ui_string(),
            'domain': case_upload_json['domain'],
            'upload_id': case_upload_json['upload_id'],
            'task_status': {
                'state': task_status.state,
                'progress': {
                    'percent': task_status.progress.percent,
                }
            }
        }

    case_uploads = [to_user_json(case_upload)
                    for case_upload in get_case_uploads(domain, limit)]
    return json_response(case_uploads)
