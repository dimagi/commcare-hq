"""
Some of these constants correspond to constants set in corehq/apps/export/static/export/js/const.js
so if changing a value, ensure that both places reflect the change
"""
from couchexport.deid import (
    deid_ID,
    deid_date
)
from corehq.apps.export.transforms import (
    case_id_to_case_name,
    user_id_to_username,
    owner_id_to_display,
)

# When fixing a bug that requires existing schemas to be rebuilt,
# bump the version number.
FORM_DATA_SCHEMA_VERSION = 8
CASE_DATA_SCHEMA_VERSION = 7

DEID_ID_TRANSFORM = "deid_id"
DEID_DATE_TRANSFORM = "deid_date"
DEID_TRANSFORM_FUNCTIONS = {
    DEID_ID_TRANSFORM: deid_ID,
    DEID_DATE_TRANSFORM: deid_date,
}
CASE_NAME_TRANSFORM = "case_name_transform"
USERNAME_TRANSFORM = "username_transform"
OWNER_ID_TRANSFORM = "owner_id_transform"
TRANSFORM_FUNCTIONS = {
    CASE_NAME_TRANSFORM: case_id_to_case_name,
    USERNAME_TRANSFORM: user_id_to_username,
    OWNER_ID_TRANSFORM: owner_id_to_display,
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
KNOWN_CASE_PROPERTIES = ["type", "name", "external_id", "user_id", "owner_id", "opened_on"]

# Attributes found on a case block. <case case_id="..." date_modified="..." ...>
CASE_ATTRIBUTES = ['@case_id', '@date_modified', '@user_id']

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
MAX_EXPORTABLE_ROWS = 100000
CASE_SCROLL_SIZE = 10000

# When a question is missing completely from a form/case this should be the value
MISSING_VALUE = '---'
# When a question has been answered, but is blank, this shoudl be the value
EMPTY_VALUE = ''

UNKNOWN_INFERRED_FROM = 'unknown'

SKIPPABLE_PROPERTIES = frozenset([
    'initial_processing_complete',
    '_rev',
    'computed_modified_on_',
    'server_modified_on',
    'domain',
    'form.#type',
    'form.@uiVersion',
    'openrosa_headers.HTTP_X_OPENROSA_VERSION',
    'openrosa_headers.HTTP_ACCEPT_LANGUAGE',
    'openrosa_headers.HTTP_DATE',
    'problem',
    'doc_type',
    'path',
    'version',
    'date_header',
    'migrating_blobs_from_couch',
    'orig_id',
    'edited_on',
    'deprecated_date',
    'deprecated_form_id',
    'auth_context.authenticated',
    'auth_context.doc_type',
    'auth_context.domain',
    'auth_context.user_id',
])
