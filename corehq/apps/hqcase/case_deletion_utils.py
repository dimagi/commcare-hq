from attrs import define, field

from casexml.apps.case.xform import extract_case_blocks, get_case_updates

from corehq.apps.hqwebapp.doc_info import get_case_url
from corehq.form_processor.interfaces.processor import CaseUpdateMetadata
from corehq.form_processor.models import CommCareCase, XFormInstance


@define
class DeleteCase:
    name = field()
    url = field()
    is_primary = field(default=False)
    delete_forms = field(factory=list)


@define
class DeleteForm:
    name = field()
    url = field()
    is_primary = field(default=False)
    affected_cases = field(factory=list)


@define
class FormAffectedCases:
    case_name = field(default=None)
    is_current_case = field(default=False)
    actions = field(factory=list)


@define
class AffectedCase:
    id = field()
    name = field()
    url = field()
    affected_forms = field(factory=list)


def get_affected_case(domain, case, affected_cases_display):
    for affected_case in affected_cases_display:
        if affected_case.id == case.case_id:
            return affected_case
    if not case.name:
        case.name = get_deleted_case_name(case)
    affected_case = AffectedCase(id=case.case_id, name=case.name, url=get_case_url(domain, case.case_id))
    affected_cases_display.append(affected_case)
    return affected_case


@define
class AffectedForm:
    name = field()
    url = field()
    actions = field()
    is_primary = field(default=False)


@define
class ReopenedCase:
    name = field()
    url = field()
    closing_form_url = field()
    closing_form_name = field()
    closing_form_is_primary = field(default=False)


def get_ordered_case_xforms(case, domain):
    # Returns deduplicated and chronologically ordered case xforms, if not already that
    revoked_inclusive_xforms = [t.form_id for t in case.transactions if t.is_form_transaction]
    xform_objs = [XFormInstance.objects.get_form(form_id, domain) for form_id in revoked_inclusive_xforms]
    case_xforms = []
    for xform in xform_objs:
        if xform not in case_xforms:
            case_xforms.append(xform)
    case_xforms = sorted(case_xforms, key=lambda form: form.received_on)
    return case_xforms


def validate_case_for_deletion(case):
    if not case.is_deleted and case.deleted_on is None:
        # Normal state - not archived nor deleted
        return case
    elif case.is_deleted and case.deleted_on is None:
        # Create form was archived > create CaseTransaction revoked > case name unassigned
        case.name = get_deleted_case_name(case)
        return case
    elif case.deleted_on:
        # Case was deleted through the proper deletion workflow, so there's no need to delete it again
        return None


def get_deleted_case_name(case):
    """When a case's create form is archived, its name is reset to '', so this process sets it again
    to properly display on the case deletion page, but does not save it to the case object"""
    create_form = ''
    for t in case.transactions:
        if t.is_case_create:
            create_form = XFormInstance.objects.get_form(t.form_id)
            break
    if not create_form:
        return '[Unknown Case]'
    case_blocks = extract_case_blocks(create_form)
    for case_block in case_blocks:
        if 'create' in case_block and case_block['@case_id'] == case.case_id:
            return case_block['create']['case_name']


def get_all_cases_from_form(form, domain):
    # A more inclusive method of getting cases from a form, including cases whose deleted field is True
    touched_cases = {}
    case_updates = get_case_updates(form)
    for update in case_updates:
        case = CommCareCase.objects.get_case(update.id, domain)
        actions = {action.action_type_slug for action in update.actions}
        case_update_meta = CaseUpdateMetadata(case, False, '', actions)
        if case.case_id in touched_cases:
            touched_cases[case.case_id] = touched_cases[case.case_id].merge(case_update_meta)
        else:
            touched_cases[case.case_id] = case_update_meta
    return touched_cases
