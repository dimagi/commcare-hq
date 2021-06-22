import attr

from casexml.apps.case.xform import extract_case_blocks

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.value_source import CaseTriggerInfo


@attr.s
class RepeaterResponse:
    """
    Ducktypes an HTTP response for Repeater.handle_response(),
    RepeatRecord.handle_success() and RepeatRecord.handle_failure()
    """
    status_code = attr.ib()
    reason = attr.ib()
    text = attr.ib(default="")
    retry = attr.ib(default=True)


def get_relevant_case_updates_from_form_json(domain, form_json, case_types, extra_fields,
                                             form_question_values=None):
    result = []
    case_blocks = extract_case_blocks(form_json)
    cases = CaseAccessors(domain).get_cases(
        [case_block['@case_id'] for case_block in case_blocks], ordered=True)

    db_case_dict = {case.case_id: case for case in cases}

    for case_block in case_blocks:
        case = db_case_dict[case_block['@case_id']]

        if not case_types or case.type in case_types:
            case_create = case_block.get('create') or {}
            case_update = case_block.get('update') or {}

            result.append(CaseTriggerInfo(
                domain=domain,
                case_id=case_block['@case_id'],
                type=case.type,
                name=case.name,
                owner_id=case.owner_id,
                modified_by=case.modified_by,
                updates={**case_create, **case_update},
                created='create' in case_block,
                closed='close' in case_block,
                extra_fields={field: case.get_case_property(field) for field in extra_fields},
                form_question_values=form_question_values or {},
            ))

    return result
