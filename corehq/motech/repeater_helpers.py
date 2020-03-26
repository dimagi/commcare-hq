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


def get_relevant_case_updates_from_form_json(domain, form_json, case_types, extra_fields,
                                             form_question_values=None):
    result = []
    case_blocks = extract_case_blocks(form_json)
    cases = CaseAccessors(domain).get_cases(
        [case_block['@case_id'] for case_block in case_blocks], ordered=True)
    for case, case_block in zip(cases, case_blocks):
        assert case_block['@case_id'] == case.case_id
        if not case_types or case.type in case_types:
            result.append(CaseTriggerInfo(
                domain=domain,
                case_id=case_block['@case_id'],
                type=case.type,
                name=case.name,
                owner_id=case.owner_id,
                modified_by=case.modified_by,
                updates=dict(
                    list(case_block.get('create', {}).items()) +
                    list(case_block.get('update', {}).items())
                ),
                created='create' in case_block,
                closed='close' in case_block,
                extra_fields={field: case.get_case_property(field) for field in extra_fields},
                form_question_values=form_question_values or {},
            ))
    return result
