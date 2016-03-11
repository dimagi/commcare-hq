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


class SystemProperty(object):
    def __init__(self, tag, name, path, description=None, transform=None, is_advanced=True):
        self.tag = tag
        self.name = name
        self.path = path
        self.description = description
        self.transform = transform
        self.is_advanced = is_advanced


PROPERTY_TAG_NONE = None
PROPERTY_TAG_INFO = 'info'
PROPERTY_TAG_UPDATE = 'update'
PROPERTY_TAG_SERVER = 'server'
PROPERTY_TAG_DELETED = 'deleted'
PROPERTY_TAG_ROW = 'row'

MAIN_TABLE_PROPERTIES = [
    SystemProperty(PROPERTY_TAG_ROW, 'number')
]

CASE_HISTORY_PROPERTIES = [
    SystemProperty(PROPERTY_TAG_NONE, 'action_type', 'action_type'),
    SystemProperty(PROPERTY_TAG_NONE, 'user_id', 'user_id'),
    SystemProperty(PROPERTY_TAG_NONE, 'date', 'date'),
    SystemProperty(PROPERTY_TAG_NONE, 'server_date', 'server_date'),
    SystemProperty(PROPERTY_TAG_NONE, 'xform_id', 'xform_id'),
    SystemProperty(PROPERTY_TAG_NONE, 'xform_xmlns', 'xform_xmlns'),
    SystemProperty(PROPERTY_TAG_NONE, 'xform_name', 'xform_name'),
    SystemProperty(PROPERTY_TAG_SERVER, 'state', 'state'),
]

FORM_EXPORT = 'form'
CASE_EXPORT = 'case'

MAIN_TABLE = []
CASE_HISTORY_TABLE = ['case_history']
