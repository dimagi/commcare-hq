from couchdbkit import ResourceNotFound
from casexml.apps.case.models import CommCareCaseGroup
from corehq.apps.hqcase.utils import get_case_by_identifier
from django.utils.translation import ugettext as _


def add_cases_to_case_group(domain, case_group_id, uploaded_data):
    response = {
        'errors': [],
        'success': [],
    }
    try:
        case_group = CommCareCaseGroup.get(case_group_id)
    except ResourceNotFound:
        response['errors'].append(_("The case group was not found."))
        return response

    for row in uploaded_data:
        identifier = row.get('case_identifier')
        case = get_case_by_identifier(domain, identifier)
        if not case:
            response['errors'].append(_("Could not find case with identifier '%s'." % identifier))
        elif case.doc_type != 'CommCareCase':
            response['errors'].append(_("It looks like the case with identifier '%s' is deleted" % identifier))
        elif case._id in case_group.cases:
            response['errors'].append(_("A case with identifier %s already exists in this group." % identifier))
        else:
            case_group.cases.append(case._id)
            response['success'].append(_("Case with identifier '%s' has been added to this group." % identifier))

    if response['success']:
        case_group.save()

    return response
