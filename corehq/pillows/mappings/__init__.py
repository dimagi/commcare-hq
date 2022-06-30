
from .app_mapping import APP_INDEX_INFO
from .case_mapping import CASE_INDEX_INFO
from .case_search_mapping import CASE_SEARCH_INDEX_INFO
from .domain_mapping import DOMAIN_INDEX_INFO
from .group_mapping import GROUP_INDEX_INFO
from .reportcase_mapping import REPORT_CASE_INDEX_INFO
from .reportxform_mapping import REPORT_XFORM_INDEX_INFO
from .sms_mapping import SMS_INDEX_INFO
from .user_mapping import USER_INDEX_INFO
from .xform_mapping import XFORM_INDEX_INFO

CANONICAL_NAME_INFO_MAP = {
    "forms": XFORM_INDEX_INFO,
    "cases": CASE_INDEX_INFO,
    "users": USER_INDEX_INFO,
    "domains": DOMAIN_INDEX_INFO,
    "apps": APP_INDEX_INFO,
    "groups": GROUP_INDEX_INFO,
    "sms": SMS_INDEX_INFO,
    "report_cases": REPORT_CASE_INDEX_INFO,
    "report_xforms": REPORT_XFORM_INDEX_INFO,
    "case_search": CASE_SEARCH_INDEX_INFO,
}
