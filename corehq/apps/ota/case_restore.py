from django.http.response import Http404

from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreContent, RestoreResponse
from casexml.apps.phone.xml import (
    get_case_element,
    get_registration_element_for_case,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase


def get_case_hierarchy_for_restore(case):
    from corehq.apps.reports.view_helpers import get_case_hierarchy
    return [c for c in get_case_hierarchy(case) if not c.closed]


def get_case_restore_response(domain, case_id):
    try:
        case = CommCareCase.objects.get_case(case_id, domain)
        if case.domain != domain or case.is_deleted:
            raise Http404
    except CaseNotFound:
        raise Http404

    with RestoreContent('Case[{}]'.format(case_id)) as content:
        content.append(get_registration_element_for_case(case))
        for case in get_case_hierarchy_for_restore(case):
            # Formplayer will be creating these cases for the first time, so
            # include create blocks
            content.append(get_case_element(case, ('create', 'update'), V2))
        payload = content.get_fileobj()

    return RestoreResponse(payload).get_http_response()
