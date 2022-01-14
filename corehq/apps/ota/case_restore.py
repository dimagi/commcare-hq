from django.http.response import Http404

from casexml.apps.case.xml import V2
from casexml.apps.phone.restore import RestoreContent, RestoreResponse
from casexml.apps.phone.xml import (
    get_case_element,
    get_registration_element_for_case,
)
from corehq.apps.locations.fixtures import (
    FlatLocationSerializer
)
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import ADD_LIMITED_FIXTURES_TO_CASE_RESTORE


def get_case_hierarchy_for_restore(case):
    from corehq.apps.reports.view_helpers import get_case_hierarchy
    return [
        c for c in get_case_hierarchy(case, {})['case_list']
        if not c.closed
    ]


def get_case_restore_response(domain, case_id):
    try:
        case = CaseAccessors(domain).get_case(case_id)
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
        if ADD_LIMITED_FIXTURES_TO_CASE_RESTORE.enabled(domain):
            _add_limited_fixtures(domain, case_id, content)
        payload = content.get_fileobj()

    return RestoreResponse(payload).get_http_response()


def _add_limited_fixtures(domain, case_id, content):
    serializer = FlatLocationSerializer()
    content.extend(serializer.get_xml_nodes(domain, 'locations', case_id,
                                            SQLLocation.active_objects.filter(domain=domain)))
