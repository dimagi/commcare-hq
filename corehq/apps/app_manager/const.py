APP_V1 = '1.0'
APP_V2 = '2.0'
MAJOR_RELEASE_TO_VERSION = {
    "1": APP_V1,
    "2": APP_V2,
}

CAREPLAN_GOAL = 'careplan_goal'
CAREPLAN_TASK = 'careplan_task'
CAREPLAN_CASE_NAMES = {
    CAREPLAN_GOAL: 'Goal',
    CAREPLAN_TASK: 'Task'
}

CT_REQUISITION_MODE_3 = '3-step'
CT_REQUISITION_MODE_4 = '4-step'
CT_REQUISITION_MODES = [CT_REQUISITION_MODE_3, CT_REQUISITION_MODE_4]

CT_LEDGER_PREFIX = 'ledger:'
CT_LEDGER_STOCK = 'stock'
CT_LEDGER_REQUESTED = 'ct-requested'
CT_LEDGER_APPROVED = 'ct-approved'

SCHEDULE_PHASE = 'current_schedule_phase'
SCHEDULE_LAST_VISIT = u'last_visit_number_{}'
SCHEDULE_LAST_VISIT_DATE = u'last_visit_date_{}'
SCHEDULE_GLOBAL_NEXT_VISIT_DATE = u'next_visit_date'
SCHEDULE_TERMINATED = '-1'
SCHEDULE_CURRENT_VISIT_NUMBER = 'current_visit_number'
SCHEDULE_UNSCHEDULED_VISIT = 'unscheduled_visit'
SCHEDULE_MAX_DATE = (2 ** 31) - 1
SCHEDULE_DATE_CASE_OPENED = u'date_opened'

ATTACHMENT_PREFIX = 'attachment:'

CASE_ID = 'case_id'
USERCASE_TYPE = 'commcare-user'
USERCASE_ID = 'usercase_id'
USERCASE_PREFIX = 'user/'

AUTO_SELECT_USER = 'user'
AUTO_SELECT_FIXTURE = 'fixture'
AUTO_SELECT_CASE = 'case'
AUTO_SELECT_LOCATION = 'location'
AUTO_SELECT_RAW = 'raw'
AUTO_SELECT_USERCASE = 'usercase'

RETURN_TO = 'return_to'

AMPLIFIES_YES = 'yes'
AMPLIFIES_NO = 'no'
AMPLIFIES_NOT_SET = 'not_set'
