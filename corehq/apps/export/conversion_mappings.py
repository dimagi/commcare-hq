from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.export.const import (
    CASE_NAME_TRANSFORM,
    USERNAME_TRANSFORM,
    OWNER_ID_TRANSFORM,
)
from corehq.apps.export.models import PathNode

# Mapping from old properties to new. Can delete once all exports have been migrated
FORM_PROPERTY_MAPPING = {
    ("form.case.@user_id", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')], None),
    ("form.case.@xmlns", None): ([PathNode(name="xmlns")], None),
    ("form.case.create.case_name", None): ([PathNode(name='form'), PathNode(name='case'), PathNode(name='create'), PathNode(name='case_name')], None),
    ("form.case.create.case_type", None): ([PathNode(name='form'), PathNode(name='case'), PathNode(name='create'), PathNode(name='case_type')], None),
    ("form.case.create.owner_id", None): ([PathNode(name='form'), PathNode(name='case'), PathNode(name='create'), PathNode(name='owner_id')], None),
    ("form.meta.@xmlns", None): ([PathNode(name='xmlns')], None),
    ("form.meta.appVersion.#text", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='appVersion')], None),
    ("form.meta.appVersion.@xmlns", None): ([PathNode(name='xmlns')], None),
    ("form.case.@case_id", "corehq.apps.export.transforms.case_id_to_case_name"): ([PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')], CASE_NAME_TRANSFORM),
    ("form.case.@case_id", None): ([PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')], None),
    ("form.meta.timeEnd", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='timeEnd')], None),
    ("form.meta.deviceID", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='deviceID')], None),
    ("form.meta.instanceID", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='instanceID')], None),
    ("_id", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='instanceID')], None),
    ("form.meta.timeStart", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='timeStart')], None),
    ("form.meta.userID", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')], None),
    ("form.meta.username", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='username')], None),
    ("app_id", None): ([PathNode(name="app_id")], None),
    ("build_id", None): ([PathNode(name="build_id")], None),
    ("doc_type", None): ([PathNode(name="doc_type")], None),
    ("domain", None): ([PathNode(name="domain")], None),
    ("edited_on", None): ([PathNode(name="edited_on")], None),
    ("last_sync_token", None): ([PathNode(name="last_sync_token")], None),
    ("partial_submission", None): ([PathNode(name="partial_submission")], None),
    ("problem", None): ([PathNode(name="problem")], None),
    ("received_on", None): ([PathNode(name="received_on")], None),
    ("submit_ip", None): ([PathNode(name="submit_ip")], None),
    ("xmlns", None): ([PathNode(name="xmlns")], None),
    ("form.@name", None): ([PathNode(name='form'), PathNode(name='@name')], None),
    ("form.@xmlns", None): ([PathNode(name="xmlns")], None),
    ("id", None): ([PathNode(name="number")], None),
    ("form.meta.location", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='location')], None),
    ("form.meta.location.#text", None): ([PathNode(name='form'), PathNode(name='meta'), PathNode(name='location')], None),
}

CASE_PROPERTY_MAPPING = {
    ("id", None): ([PathNode(name="number")], None),
    ("_id", None): ([PathNode(name='_id')], None),
    ('type', None): ([PathNode(name='type')], None),
    ('closed', None): ([PathNode(name='closed')], None),
    ('closed_by', None): ([PathNode(name='closed_by')], None),
    ('closed_by', 'corehq.apps.export.transforms.user_id_to_username'): ([PathNode(name='closed_by')], USERNAME_TRANSFORM),
    ('closed_on', None): ([PathNode(name='closed_on')], None),
    ('external_id', None): ([PathNode(name='external_id')], None),
    ('user_id', None): ([PathNode(name='user_id')], None),
    ('user_id', 'corehq.apps.export.transforms.user_id_to_username'): ([PathNode(name='user_id')], USERNAME_TRANSFORM),
    ('modified_on', None): ([PathNode(name='modified_on')], None),
    ('opened_by', None): ([PathNode(name='opened_by')], None),
    ('opened_by', 'corehq.apps.export.transforms.user_id_to_username'): ([PathNode(name='opened_by')], USERNAME_TRANSFORM),
    ('opened_on', None): ([PathNode(name='opened_on')], None),
    ('owner_id', None): ([PathNode(name='owner_id')], None),
    ('owner_id', 'corehq.apps.export.transforms.owner_id_to_display'): ([PathNode(name='owner_id')], OWNER_ID_TRANSFORM),
    ('server_modified_on', None): ([PathNode(name='server_modified_on')], None),
    ('doc_type', None): ([PathNode(name='doc_type')], None),
}

CASE_HISTORY_PROPERTY_MAPPING = {
    ("id", None): ([PathNode(name="number")], None),
    ('action_type', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='action_type')], None),
    ('user_id', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='user_id')], None),
    ('server_date', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='server_date')], None),
    ('xform_id', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='xform_id')], None),
    ('xform_name', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='xform_name')], None),
    ('xform_xmlns', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='xform_xmlns')], None),
    ('deprecated', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='deprecated')], None),
    ('sync_log_id', None): ([PathNode(name='actions', is_repeat=True), PathNode(name='sync_log_id')], None),
}

PARENT_CASE_PROPERTY_MAPPING = {
    ('id', None): ([PathNode(name='number')], None),
    ('referenced_id', None): ([PathNode(name='indices', is_repeat=True), PathNode(name='referenced_id')], None),
    ('referenced_type', None): ([PathNode(name='indices', is_repeat=True), PathNode(name='referenced_type')], None),
    ('identifier', None): ([PathNode(name='indices', is_repeat=True), PathNode(name='relationship')], None),
    ('doc_type', None): ([PathNode(name='indices', is_repeat=True), PathNode(name='doc_type')], None),
}

REPEAT_GROUP_PROPERTY_MAPPING = {
    ('id', None): ([PathNode(name='number')], None),
}
