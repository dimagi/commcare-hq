"""
Some of these constants correspond to constants set in corehq/apps/export/static/export/js/const.js
so if changing a value, ensure that both places reflect the change
"""
from collections import namedtuple

DEID_TRANSFORM_FUNCTIONS = {
    'deid_id': lambda x: x,  # TODO: map these to actual deid functions
    'deid_date': lambda x: x,
}
TRANSFORM_FUNCTIONS = {
}
TRANSFORM_FUNCTIONS.update(DEID_TRANSFORM_FUNCTIONS)

SystemProperty = namedtuple('SystemProperty', ['tag', 'name'])

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
    SystemProperty(PROPERTY_TAG_NONE, 'action_type'),
    SystemProperty(PROPERTY_TAG_NONE, 'user_id'),
    SystemProperty(PROPERTY_TAG_NONE, 'date'),
    SystemProperty(PROPERTY_TAG_NONE, 'server_date'),
    SystemProperty(PROPERTY_TAG_NONE, 'xform_id'),
    SystemProperty(PROPERTY_TAG_NONE, 'xform_xmlns'),
    SystemProperty(PROPERTY_TAG_NONE, 'xform_name'),
    SystemProperty(PROPERTY_TAG_SERVER, 'state'),
]

FORM_EXPORT = 'form'
CASE_EXPORT = 'case'

MAIN_TABLE = []
CASE_HISTORY_TABLE = ['case_history']
