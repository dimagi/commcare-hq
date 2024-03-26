from attrs import define, field

from casexml.apps.case.xform import get_case_updates

from corehq.apps.hqwebapp.doc_info import get_case_url
from corehq.form_processor.interfaces.processor import CaseUpdateMetadata


@define
class DeleteCase:
    id = field()
    name = field()
    url = field()
    is_primary = field(default=False)
    delete_forms = field(factory=list)


@define
class DeleteForm:
    id = field()
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


def get_or_create_affected_case(domain, case, affected_cases_display, form_cache, case_block_cache):
    """Note: affected_cases_display is additionally mutated by this function"""
    for affected_case in affected_cases_display:
        if affected_case.id == case.case_id:
            return affected_case
    if not case.name:
        case.name = _get_deleted_case_name(case, form_cache, case_block_cache)
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


def get_deduped_ordered_forms_for_case(case, form_cache):
    """
    Returns deduplicated and chronologically ordered case xforms, if not already that.
    Returned forms are inclusive of forms from revoked CaseTransactions (necessary in order to include
    archived forms in the deletion workflow), which the case.xform_ids method does not support.
    """
    revoked_inclusive_xform_ids = list({t.form_id for t in case.transactions if t.is_form_transaction})
    xform_objs = form_cache.get_forms(revoked_inclusive_xform_ids)
    return sorted(xform_objs, key=lambda form: form.received_on)


def prepare_case_for_deletion(case, form_cache, case_block_cache):
    if not case.is_deleted and case.deleted_on is None:
        # Normal state - not archived nor deleted
        return case
    elif case.is_deleted and case.deleted_on is None:
        # Create form was archived > create CaseTransaction revoked > case name unassigned
        case.name = _get_deleted_case_name(case, form_cache, case_block_cache)
        return case
    elif case.deleted_on:
        # Case was deleted through the proper deletion workflow, so there's no need to delete it again
        return None


def _get_deleted_case_name(case, form_cache, case_block_cache):
    """When a case's create form is archived, its name is reset to '', so this process sets it again
    to properly display on the case deletion page, but does not save it to the case object"""
    for t in case.transactions:
        if t.is_case_create:
            form_list = form_cache.get_forms([t.form_id])
            if form_list:
                create_form = form_list[0]
                break
            continue
    else:
        return '[Unknown Case]'
    case_blocks = case_block_cache.get_case_blocks(create_form)
    for case_block in case_blocks:
        if 'create' in case_block and case_block['@case_id'] == case.case_id:
            return case_block['create']['case_name']


def get_all_cases_from_form(form, case_cache, case_block_cache):
    case_updates = get_case_updates(form, case_block_cache=case_block_cache)
    update_ids = [update.id for update in case_updates]
    all_cases = case_cache.get_cases(update_ids)
    all_actions = [{action.action_type_slug for action in update.actions} for update in case_updates]

    touched_cases = {}
    for case, actions in zip(all_cases, all_actions):
        case_update_meta = CaseUpdateMetadata(case, False, '', actions)
        if case.case_id in touched_cases:
            touched_cases[case.case_id] = touched_cases[case.case_id].merge(case_update_meta)
        else:
            touched_cases[case.case_id] = case_update_meta
    return touched_cases
