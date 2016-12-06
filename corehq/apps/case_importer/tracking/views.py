from corehq.apps.case_importer.tracking.dbaccessors import get_case_uploads
from corehq.apps.case_importer.views import require_can_edit_data
from dimagi.utils.web import json_response


@require_can_edit_data
def case_uploads(request, domain):
    try:
        limit = int(request.GET.get('limit'))
    except (TypeError, ValueError):
        limit = 10

    case_uploads = get_case_uploads(domain, limit)
    return json_response(case_uploads)
