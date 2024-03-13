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

STOCK_QUESTION_TAG_NAMES = [
    'balance',
    'transfer',
]


MOBILE_UCR_VERSION_1 = '1.0'
MOBILE_UCR_MIGRATING_TO_2 = '1.5'
MOBILE_UCR_VERSION_2 = '2.0'
MOBILE_UCR_VERSIONS = [MOBILE_UCR_VERSION_1, MOBILE_UCR_MIGRATING_TO_2, MOBILE_UCR_VERSION_2]

DEFAULT_LOCATION_FIXTURE_OPTION = 'project_default'
LOCATION_FIXTURE_OPTIONS = [
    DEFAULT_LOCATION_FIXTURE_OPTION,
    'both_fixtures',
    'only_flat_fixture',
    'only_hierarchical_fixture'
]
SYNC_HIERARCHICAL_FIXTURE = ('both_fixtures', 'only_hierarchical_fixture')
SYNC_FLAT_FIXTURES = ('both_fixtures', 'only_flat_fixture')

TARGET_COMMCARE = 'commcare'
TARGET_COMMCARE_LTS = 'commcare_lts'

WORKFLOW_DEFAULT = 'default'  # go to the app main screen
WORKFLOW_ROOT = 'root'  # go to the module select screen
WORKFLOW_PARENT_MODULE = 'parent_module'  # go to the parent module's screen
WORKFLOW_MODULE = 'module'  # go to the current module's screen
WORKFLOW_PREVIOUS = 'previous_screen'  # go to the previous screen (prior to entering the form)
WORKFLOW_FORM = 'form'  # go straight to another form or menu
ALL_WORKFLOWS = [
    WORKFLOW_DEFAULT,
    WORKFLOW_ROOT,
    WORKFLOW_PARENT_MODULE,
    WORKFLOW_MODULE,
    WORKFLOW_PREVIOUS,
    WORKFLOW_FORM,
]
# allow all options as fallback except the one for form linking
WORKFLOW_FALLBACK_OPTIONS = list(ALL_WORKFLOWS).remove(WORKFLOW_FORM)

WORKFLOW_CASE_LIST = 'case_list'  # Return back to the case list after registering a case
REGISTRATION_FORM_WORFLOWS = [
    WORKFLOW_DEFAULT,
    WORKFLOW_CASE_LIST,
]

REGISTRY_WORKFLOW_LOAD_CASE = 'load_case'
REGISTRY_WORKFLOW_SMART_LINK = 'smart_link'

UPDATE_MODE_ALWAYS, UPDATE_MODE_EDIT = 'always', 'edit'

MULTI_SELECT_MAX_SELECT_VALUE = 100

DEFAULT_PAGE_LIMIT = 10

CALCULATED_SORT_FIELD_RX = r'^_cc_calculated_(\d+)$'

CASE_LIST_FILTER_LOCATIONS_FIXTURE = 'Locations Fixture'
