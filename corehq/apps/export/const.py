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

# Mapping from old properties to new. Can delete once all exports have been migrated
FORM_PROPERTY_MAPPING = {
    ("form.case.@date_modified", None): ("", None),
    ("form.case.@user_id", None): ("form.meta.userID", None),
    ("form.case.@xmlns", None): ("xmlns", None),
    ("form.case.create.case_name", None): ('form.case.create.case_name', None),
    ("form.case.create.case_type", None): ('form.case.create.case_type', None),
    ("form.case.create.owner_id", None): ('form.case.create.owner_id', None),
    ("form.meta.@xmlns", None): ('xmlns', None),
    ("form.meta.appVersion.#text", None): ('form.meta.appVersion', None),
    ("form.meta.appVersion.@xmlns", None): ('xmlns', None),
    ("form.case.@case_id", None): ("form.case.@case_id", "corehq.apps.export.transforms.case_id_to_case_name"),
    ("form.case.@case_id", None): ("form.case.@case_id", None),
    ("form.meta.timeEnd", None): ("form.meta.timeEnd", None),
    ("form.meta.deviceID", None): ("form.meta.deviceID", None),
    ("form.meta.instanceID", None): ("form.meta.instanceID", None),
    ("_id", None): ("form.meta.instanceID", None),
    ("form.meta.timeStart", None): ("form.meta.timeStart", None),
    ("form.meta.userID", None): ("form.meta.userID", None),
    ("form.meta.username", None): ("form.meta.username", None),
    ("app_id", None): ("app_id", None),
    ("build_id", None): ("build_id", None),
    ("doc_type", None): ("doc_type", None),
    ("domain", None): ("domain", None),
    ("edited_on", None): ("edited_on", None),
    ("last_sync_token", None): ("last_sync_token", None),
    ("partial_submission", None): ("partial_submission", None),
    ("problem", None): ("problem", None),
    ("received_on", None): ("received_on", None),
    ("submit_ip", None): ("submit_ip", None),
    ("xmlns", None): ("xmlns", None),
    ("form.@name", None): ("form.@name", None),
    ("form.@xmlns", None): ("xmlns", None),
}
