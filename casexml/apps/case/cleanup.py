from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import get_case_xform_ids
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.case.xml.parser import case_update_from_block
from couchforms.models import get as get_form

def rebuild_case(case_id):
    """
    Given a case ID, rebuild the entire case state based on all existing forms
    referencing it. Useful when things go wrong or when you need to manually
    rebuild a case afer archiving / deliting it
    """
    case = CommCareCase.get(case_id)

    # clear actions and xform_ids
    case.xform_ids = []
    case.actions = []

    form_ids = get_case_xform_ids(case_id)
    forms = [get_form(id) for id in form_ids]
    filtered_forms = [f for f in forms if f.doc_type == "XFormInstance"]
    sorted_forms = sorted(filtered_forms, key=lambda f: f.received_on)
    for form in sorted_forms:
        assert form.domain == case.domain
        case_blocks = extract_case_blocks(form)
        case_updates = [case_update_from_block(case_block) for case_block in case_blocks]
        filtered_updates = [u for u in case_updates if u.id == case_id]
        for u in filtered_updates:
            case.update_from_case_update(u, form)
    case.xform_ids = [f._id for f in sorted_forms]
    case.save()
    return case
