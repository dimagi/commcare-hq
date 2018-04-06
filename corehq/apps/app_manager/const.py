from __future__ import unicode_literals
APP_V1 = '1.0'
APP_V2 = '2.0'
MAJOR_RELEASE_TO_VERSION = {
    "1": APP_V1,
    "2": APP_V2,
}

SCHEDULE_PHASE = 'current_schedule_phase'
SCHEDULE_LAST_VISIT = 'last_visit_number_{}'
SCHEDULE_LAST_VISIT_DATE = 'last_visit_date_{}'
SCHEDULE_GLOBAL_NEXT_VISIT_DATE = 'next_visit_date'
SCHEDULE_NEXT_DUE = 'next_due'
SCHEDULE_TERMINATED = '-1'
SCHEDULE_CURRENT_VISIT_NUMBER = 'current_visit_number'
SCHEDULE_UNSCHEDULED_VISIT = 'unscheduled_visit'
SCHEDULE_MAX_DATE = (2 ** 31) - 1
SCHEDULE_DATE_CASE_OPENED = 'date_opened'

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

DEFAULT_MONTH_FILTER_PERIOD_LENGTH = 0

CLAIM_DEFAULT_RELEVANT_CONDITION = "count(instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/case_id]) = 0"

STOCK_QUESTION_TAG_NAMES = [
    'balance',
    'transfer',
]

DEFAULT_FETCH_LIMIT = 5

APP_TRANSLATION_UPLOAD_FAIL_MESSAGE = (
    "Translation Upload Failed! "
    "Please make sure you are using a valid Excel 2007 or later (.xlsx) file. "
    "Error details: {}."
)

MOBILE_UCR_VERSION_1 = '1.0'
MOBILE_UCR_MIGRATING_TO_2 = '1.5'
MOBILE_UCR_VERSION_2 = '2.0'
MOBILE_UCR_VERSIONS = [MOBILE_UCR_VERSION_1, MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2]
