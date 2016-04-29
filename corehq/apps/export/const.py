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


FORM_EXPORT = 'form'
CASE_EXPORT = 'case'
