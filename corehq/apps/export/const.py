from collections import namedtuple

SystemProperty = namedtuple('SystemProperty', ['tag', 'name'])

PROPERTY_TAG_NONE = None
PROPERTY_TAG_INFO = 'info'
PROPERTY_TAG_UPDATE = 'update'
PROPERTY_TAG_SERVER = 'server'

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
CASE_HISTORY_GROUP_NAME = 'history'

FORM_EXPORT = 'form'
CASE_EXPORT = 'case'

MAIN_TABLE = None
