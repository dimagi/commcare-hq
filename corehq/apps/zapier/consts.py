from corehq.motech.repeaters.models import (
    CaseRepeater,
    CreateCaseRepeater,
    SQLUpdateCaseRepeater,
)


class EventTypes(object):
    NEW_FORM = 'new_form'
    NEW_CASE = 'new_case'
    UPDATE_CASE = 'update_case'
    CHANGED_CASE = 'changed_case'  # includes both new and updated


CASE_TYPE_REPEATER_CLASS_MAP = {
    EventTypes.NEW_CASE: CreateCaseRepeater,
    EventTypes.UPDATE_CASE: SQLUpdateCaseRepeater,
    EventTypes.CHANGED_CASE: CaseRepeater,
}
