"""
Some of these constants correspond to constants set in corehq/apps/export/static/export/js/const.js
so if changing a value, ensure that both places reflect the change
"""
from couchexport.deid import deid_date, deid_ID

from corehq.apps.export.transforms import (
    case_close_to_boolean,
    case_id_to_case_name,
    case_id_to_link,
    case_or_user_id_to_name,
    doc_type_transform,
    form_id_to_link,
    owner_id_to_display,
    user_id_to_username,
    workflow_transform,
)

# When fixing a bug that requires existing schemas to be rebuilt,
# bump the version number.
FORM_DATA_SCHEMA_VERSION = 10
CASE_DATA_SCHEMA_VERSION = 8
SMS_DATA_SCHEMA_VERSION = 1

DEID_ID_TRANSFORM = "deid_id"
DEID_DATE_TRANSFORM = "deid_date"
DEID_TRANSFORM_FUNCTIONS = {
    DEID_ID_TRANSFORM: deid_ID,
    DEID_DATE_TRANSFORM: deid_date,
}
CASE_NAME_TRANSFORM = "case_name_transform"
CASE_ID_TO_LINK = "case_link_transform"
FORM_ID_TO_LINK = "form_link_transform"
USERNAME_TRANSFORM = "username_transform"
OWNER_ID_TRANSFORM = "owner_id_transform"
WORKFLOW_TRANSFORM = "workflow_transform"
DOC_TYPE_TRANSFORM = "doc_type_transform"
CASE_OR_USER_ID_TRANSFORM = "case_or_user_id_transform"
CASE_CLOSE_TO_BOOLEAN = "case_close_to_boolean"
TRANSFORM_FUNCTIONS = {
    CASE_NAME_TRANSFORM: case_id_to_case_name,
    CASE_ID_TO_LINK: case_id_to_link,
    FORM_ID_TO_LINK: form_id_to_link,
    USERNAME_TRANSFORM: user_id_to_username,
    OWNER_ID_TRANSFORM: owner_id_to_display,
    WORKFLOW_TRANSFORM: workflow_transform,
    DOC_TYPE_TRANSFORM: doc_type_transform,
    CASE_OR_USER_ID_TRANSFORM: case_or_user_id_to_name,
    CASE_CLOSE_TO_BOOLEAN: case_close_to_boolean,
}
PLAIN_USER_DEFINED_SPLIT_TYPE = 'plain'
MULTISELCT_USER_DEFINED_SPLIT_TYPE = 'multi-select'
USER_DEFINED_SPLIT_TYPES = [
    PLAIN_USER_DEFINED_SPLIT_TYPE,
    MULTISELCT_USER_DEFINED_SPLIT_TYPE,
]


PROPERTY_TAG_NONE = None
PROPERTY_TAG_INFO = 'info'
PROPERTY_TAG_CASE = 'case'
PROPERTY_TAG_UPDATE = 'update'
PROPERTY_TAG_SERVER = 'server'
PROPERTY_TAG_DELETED = 'deleted'
PROPERTY_TAG_ROW = 'row'
PROPERTY_TAG_APP = "app"
PROPERTY_TAG_STOCK = 'stock'

# Yeah... let's not hard code this list everywhere
# This list comes from casexml.apps.case.xml.parser.CaseActionBase.from_v2
KNOWN_CASE_PROPERTIES = [
    "type",
    "case_type",
    "name",
    "case_name",
    "external_id",
    "user_id",
    "owner_id",
    "opened_on",
]

# Attributes found on a case block. <case case_id="..." date_modified="..." ...>
CASE_ATTRIBUTES = {
    '@case_id': 'string',
    '@date_modified': 'datetime',
    '@user_id': 'string'
}

# Elements that are found in a case create block
# <case>
#   <create>
#       <case_name>
#       ...
#   </create>
# </case>
CASE_CREATE_ELEMENTS = ['case_name', 'owner_id', 'case_type']

FORM_EXPORT = 'form'
CASE_EXPORT = 'case'
SMS_EXPORT = 'sms'
MAX_NORMAL_EXPORT_SIZE = 100000
MAX_DAILY_EXPORT_SIZE = 1000000
CASE_SCROLL_SIZE = 10000

# When a question is missing completely from a form/case this should be the value
MISSING_VALUE = '---'
# When a question has been answered, but is blank, this should be the value
EMPTY_VALUE = ''

UNKNOWN_INFERRED_FROM = 'unknown'

# Used for manually triggered exports
EXPORT_DOWNLOAD_QUEUE = 'export_download_queue'
# Used for automatically triggered exports
SAVED_EXPORTS_QUEUE = 'saved_exports_queue'

# The maximum file size of one DataFile
MAX_DATA_FILE_SIZE = 104857600  # 100 MB

# The total space allowance of a domain for DataFiles
MAX_DATA_FILE_SIZE_TOTAL = 2147483648  # 2 GB

MAX_MULTIMEDIA_EXPORT_SIZE = 5 * 1024**3  # 5GB


class SharingOption(object):
    PRIVATE = 'private'
    EXPORT_ONLY = 'export_only'
    EDIT_AND_EXPORT = 'edit_and_export'

    CHOICES = (
        PRIVATE,
        EXPORT_ONLY,
        EDIT_AND_EXPORT,
    )


UNKNOWN_EXPORT_OWNER = 'unknown'

EXPORT_FAILURE_TOO_LARGE = 'too_large'
EXPORT_FAILURE_UNKNOWN = 'unknown'

# For bulk case exports
ALL_CASE_TYPE_EXPORT = 'commcare-all-case-types'

# Key for saving bulk case export task progress to cache
BULK_CASE_EXPORT_CACHE = 'bulk-case-export-task'

# Max limits allowed for being able to do a bulk case export
MAX_CASE_TYPE_COUNT = 30
MAX_APP_COUNT = 20
EXCEL_MAX_SHEET_NAME_LENGTH = 31
