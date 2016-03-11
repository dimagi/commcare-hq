"""
Some of these constants correspond to constants set in corehq/apps/export/static/export/js/const.js
so if changing a value, ensure that both places reflect the change
"""
from django.utils.translation import ugettext_lazy as _
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
PROPERTY_TAG_CASE = 'case'
PROPERTY_TAG_UPDATE = 'update'
PROPERTY_TAG_SERVER = 'server'
PROPERTY_TAG_DELETED = 'deleted'
PROPERTY_TAG_ROW = 'row'
PROPERTY_TAG_APP = "app"

# System properties to be displayed above the form questions
TOP_MAIN_FORM_TABLE_PROPERTIES = [
    SystemProperty(PROPERTY_TAG_ROW, "number", "number", is_advanced=False),
    SystemProperty(PROPERTY_TAG_INFO, 'formid', 'form.meta.instanceID', _('Unique identifier of the form submission'), is_advanced=False),
]

# System properties to be displayed below the form questions
BOTTOM_MAIN_FORM_TABLE_PROPERTIES = [
    SystemProperty(PROPERTY_TAG_INFO, 'completed_time', 'form.meta.timeEnd', _('The time at which this form was completed'), is_advanced=False),
    SystemProperty(PROPERTY_TAG_INFO, 'username', 'form.meta.username', _('The user who submitted this form'), is_advanced=False),
    SystemProperty(PROPERTY_TAG_INFO, 'userID', 'form.meta.userID', _("The id of the user who submitted this form")),
    SystemProperty(PROPERTY_TAG_INFO, '@xmlns', 'xmlns', _('The xmlns of this form')),
    SystemProperty(PROPERTY_TAG_INFO, '@name', 'form.@name', _('The name of this form')),
    SystemProperty(PROPERTY_TAG_INFO, 'App Version', 'form.meta.appVersion', _('The version of CommCare that was used to submit this form')),
    SystemProperty(PROPERTY_TAG_INFO, 'deviceID', 'form.meta.deviceID', _("The id of the device that submitted this form")),


    SystemProperty(PROPERTY_TAG_APP, 'app_id', 'app_id', _("The id of the app that this form is part of")),
    SystemProperty(PROPERTY_TAG_APP, 'build_id', 'build_id', _("The id of the app version that this form is part of")),
    SystemProperty(PROPERTY_TAG_APP, '@version', 'form.@version', _("The app version number that this form is part of")),


    SystemProperty(PROPERTY_TAG_SERVER, "state", "doc_type"),
    SystemProperty(PROPERTY_TAG_SERVER, "last_sync_token", _("last_sync_token")),
    SystemProperty(PROPERTY_TAG_SERVER, "partial_submission", "partial_submission", _("True if the form was a partial submission, False otherwise.")),
    SystemProperty(PROPERTY_TAG_SERVER, "received_on", "received_on", _("The time at which the server receive this form submission"), is_advanced=False),
    SystemProperty(PROPERTY_TAG_SERVER, "submit_ip", "submit_ip", _("The IP address from which the form was submitted")),



    SystemProperty(PROPERTY_TAG_CASE, 'caseid', 'form.case.@case_id', _('The id of the case that this form operated on'), is_advanced=False),
    SystemProperty(PROPERTY_TAG_CASE, 'case_name', 'form.case.@case_id', _("The name of the case that this form operated on"), CASE_NAME_TRANSFORM, is_advanced=False),
    SystemProperty(PROPERTY_TAG_CASE, 'create.case_name', 'form.case.create.case_name', _('The name of the case that this form opened')),
    SystemProperty(PROPERTY_TAG_CASE, 'create.case_type', 'form.case.create.case_type', _('The type of the case that this form opened')),
    SystemProperty(PROPERTY_TAG_CASE, 'create.owner_id', 'form.case.create.owner_id', _('The owner id of the case that this form opened')),
]
MAIN_FORM_TABLE_PROPERTIES = TOP_MAIN_FORM_TABLE_PROPERTIES + BOTTOM_MAIN_FORM_TABLE_PROPERTIES


MAIN_CASE_TABLE_PROPERTIES = [
    SystemProperty(PROPERTY_TAG_INFO, 'caseid', '_id', _("The id of the case")),
    SystemProperty(PROPERTY_TAG_INFO, 'case_type', 'type', _("The type of the case")),
    SystemProperty(PROPERTY_TAG_INFO, 'closed', 'closed', _("True if the case is closed, otherwise False")),
    SystemProperty(PROPERTY_TAG_INFO, 'closed_by_user_id', 'closed_by', _("The id of the user who closed the case"), ),
    SystemProperty(PROPERTY_TAG_INFO, 'closed_by_username', 'closed_by', _("The username of the user who closed the case"), USERNAME_TRANSFORM),
    SystemProperty(PROPERTY_TAG_INFO, 'closed_date', 'closed_on', _("The date and time at which the case was closed")),
    SystemProperty(PROPERTY_TAG_INFO, 'external_id', 'external_id', _("The external id for this case")),
    SystemProperty(PROPERTY_TAG_INFO, 'last_modified_by_user_id', 'user_id', _("The id of the user who last modified this case")),
    SystemProperty(PROPERTY_TAG_INFO, 'last_modified_by_user_username', 'user_id', _("The username of the user who last modified this case"), USERNAME_TRANSFORM),
    SystemProperty(PROPERTY_TAG_INFO, 'last_modified_date', 'modified_on', _("The date and time at which the case was last modified")),
    SystemProperty(PROPERTY_TAG_INFO, 'opened_by_user_id', 'opened_by', _("The id of the user who opened the case")),
    SystemProperty(PROPERTY_TAG_INFO, 'opened_by_username', 'opened_by', _("The username of the user who opened the case"), USERNAME_TRANSFORM),
    SystemProperty(PROPERTY_TAG_INFO, 'opened_date', 'opened_on', _("The date and time at which the case was opened")),
    SystemProperty(PROPERTY_TAG_INFO, 'owner_id', 'owner_id', _("The id of the user who owns the case")),
    SystemProperty(PROPERTY_TAG_INFO, 'owner_name', 'owner_id', _("The username of the user who owns the case"), USERNAME_TRANSFORM),
    SystemProperty(PROPERTY_TAG_INFO, 'server_last_modified_date', 'server_modified_on', _("The date and time at which the server received the form that last modified the case"), USERNAME_TRANSFORM),
    SystemProperty(PROPERTY_TAG_INFO, 'doc_typ', 'doc_typ'),
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
