from corehq.motech.repeaters.models import (
    SQLCaseRepeater,
    SQLCreateCaseRepeater,
    SQLUpdateCaseRepeater,
)


class EventTypes(object):
    NEW_FORM = 'new_form'
    NEW_CASE = 'new_case'
    UPDATE_CASE = 'update_case'
    CHANGED_CASE = 'changed_case'  # includes both new and updated


CASE_TYPE_REPEATER_CLASS_MAP = {
    EventTypes.NEW_CASE: SQLCreateCaseRepeater,
    EventTypes.UPDATE_CASE: SQLUpdateCaseRepeater,
    EventTypes.CHANGED_CASE: SQLCaseRepeater,
}
