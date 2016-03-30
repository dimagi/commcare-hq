"""
Some of these constants correspond to constants set in corehq/apps/export/static/export/js/const.js
so if changing a value, ensure that both places reflect the change
"""
from corehq.apps.export.transforms import case_id_to_case_name, \
    user_id_to_username

DEID_TRANSFORM_FUNCTIONS = {
    'deid_id': lambda x: x,  # TODO: map these to actual deid functions
    'deid_date': lambda x: x,
}
CASE_NAME_TRANSFORM = "case_name_transform"
USERNAME_TRANSFORM = "username_transform"
TRANSFORM_FUNCTIONS = {
    CASE_NAME_TRANSFORM: case_id_to_case_name,
    USERNAME_TRANSFORM: user_id_to_username,
}
TRANSFORM_FUNCTIONS.update(DEID_TRANSFORM_FUNCTIONS)


PROPERTY_TAG_NONE = None
PROPERTY_TAG_INFO = 'info'
PROPERTY_TAG_CASE = 'case'
PROPERTY_TAG_UPDATE = 'update'
PROPERTY_TAG_SERVER = 'server'
PROPERTY_TAG_DELETED = 'deleted'
PROPERTY_TAG_ROW = 'row'
PROPERTY_TAG_APP = "app"


FORM_EXPORT = 'form'
CASE_EXPORT = 'case'
