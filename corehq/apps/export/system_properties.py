# TODO: Can't store a translation like this on the dataschema. Translate it somewhere else instead.
#from django.utils.translation import ugettext_lazy as _
def _(s):
    return s

from corehq.apps.export.const import (
    PROPERTY_TAG_ROW,
    PROPERTY_TAG_INFO,
    PROPERTY_TAG_APP,
    PROPERTY_TAG_SERVER,
    PROPERTY_TAG_CASE,
    CASE_NAME_TRANSFORM,
    USERNAME_TRANSFORM,
    PROPERTY_TAG_NONE)
from corehq.apps.export.models import ExportColumn, ExportItem
from corehq.apps.export.models.new import PathNode

# System properties to be displayed above the form questions
TOP_MAIN_FORM_TABLE_PROPERTIES = [
    ExportColumn(
        tags=[PROPERTY_TAG_ROW],
        label="number",
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label="formid",
        item=ExportItem(path=[
            PathNode(name='form'),
            PathNode(name='meta'),
            PathNode(name='instnaceID')
        ]),
        help_text=_('Unique identifier of the form submission'),
        selected=True,
    )
]

# System properties to be displayed below the form questions
BOTTOM_MAIN_FORM_TABLE_PROPERTIES = [
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='completed_time',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='timeEnd')
        ]),
        help_text=_('The time at which this form was completed'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='username',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='username')
        ]),
        help_text=_('The user who submitted this form'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='userID',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')
        ]),
        is_advanced=True,
        help_text=_("The id of the user who submitted this form")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='@xmlns',
        item=ExportItem(path=[PathNode(name='xmlns')]),
        is_advanced=True,
        help_text=_('The xmlns of this form')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='@name',
        item=ExportItem(path=[PathNode(name='form'), PathNode(name='@name')]),
        is_advanced=True,
        help_text=_('The name of this form')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='App Version',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='appVersion')
        ]),
        is_advanced=True,
        help_text=_('The version of CommCare that was used to submit this form')),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='deviceID',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='deviceID')
        ]),
        is_advanced=True,
        help_text=_("The id of the device that submitted this form")
    ),


    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='app_id',
        item=ExportItem(path=[PathNode(name='app_id')]),
        is_advanced=True,
        help_text=_("The id of the app that this form is part of")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='build_id',
        item=ExportItem(path=[PathNode(name='build_id')]),
        is_advanced=True,
        help_text=_("The id of the app version that this form is part of")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='@version',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='@version')
        ]),
        is_advanced=True,
        help_text=_("The app version number that this form is part of")
    ),


    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="state",
        item=ExportItem(path=[PathNode(name="doc_type")]),
        is_advanced=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="last_sync_token",
        item=ExportItem(path=[PathNode(name="last_sync_token")]),
        is_advanced=True,
        help_text=_("last_sync_token")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="partial_submission",
        item=ExportItem(path=[PathNode(name="partial_submission")]),
        is_advanced=True,
        help_text=_("True if the form was a partial submission, False otherwise.")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="received_on",
        item=ExportItem(path=[PathNode(name="received_on")]),
        selected=True,
        help_text=_("The time at which the server receive this form submission"),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="submit_ip",
        item=ExportItem(path=[PathNode(name="submit_ip")]),
        is_advanced=True,
        help_text=_("The IP address from which the form was submitted")
    ),


    ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='caseid',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')
        ]),
        selected=True,
        help_text=_('The id of the case that this form operated on')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='case_name',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')
        ]),
        selected=True,
        transforms=[CASE_NAME_TRANSFORM],
        help_text=_("The name of the case that this form operated on")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='create.case_name',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='case'), PathNode(name='create'), PathNode(name='case_name')
        ]),
        is_advanced=True,
        help_text=_('The name of the case that this form opened')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='create.case_type',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='case'), PathNode(name='create'), PathNode(name='case_type')
        ]),
        is_advanced=True,
        help_text=_('The type of the case that this form opened')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='create.owner_id',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='case'), PathNode(name='create'), PathNode(name='owner_id')]
        ),
        is_advanced=True,
        help_text=_('The owner id of the case that this form opened')
    ),
]
MAIN_FORM_TABLE_PROPERTIES = TOP_MAIN_FORM_TABLE_PROPERTIES + BOTTOM_MAIN_FORM_TABLE_PROPERTIES

ROW_NUMBER_COLUMN = ExportColumn(
    tags=[PROPERTY_TAG_ROW],
    label='number',
    item=ExportItem(path=[PathNode(name='number')]),
)

TOP_MAIN_CASE_TABLE_PROPERTIES = [
    # This first list is displayed above the case properties
    ExportColumn(
        tags=[PROPERTY_TAG_ROW],
        label='number',
        item=ExportItem(path=[PathNode(name='number')]),
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='caseid',
        item=ExportItem(path=[PathNode(name='_id')]),
        help_text=_("The id of the case"),
        selected=True
    ),
]

BOTTOM_MAIN_CASE_TABLE_PROPERTIES = [
    # This second list is displayed below the case properties
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='case_type',
        item=ExportItem(path=[PathNode(name='type')]),
        help_text=_("The type of the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='closed',
        item=ExportItem(path=[PathNode(name='closed')]),
        help_text=_("True if the case is closed, otherwise False"),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='closed_by_user_id',
        item=ExportItem(path=[PathNode(name='closed_by')]),
        help_text=_("The id of the user who closed the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='closed_by_username',
        item=ExportItem(path=[PathNode(name='closed_by')]),
        help_text=_("The username of the user who closed the case"),
        transforms=[USERNAME_TRANSFORM],
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='closed_date',
        item=ExportItem(path=[PathNode(name='closed_on')]),
        help_text=_("The date and time at which the case was closed"),
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='external_id',
        item=ExportItem(path=[PathNode(name='external_id')]),
        help_text=_("The external id for this case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='last_modified_by_user_id',
        item=ExportItem(path=[PathNode(name='user_id')]),
        help_text=_("The id of the user who last modified this case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='last_modified_by_user_username',
        item=ExportItem(path=[PathNode(name='user_id')]),
        help_text=_("The username of the user who last modified this case"),
        transforms=[USERNAME_TRANSFORM],
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='last_modified_date',
        item=ExportItem(path=[PathNode(name='modified_on')]),
        help_text=_("The date and time at which the case was last modified"),
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='opened_by_user_id',
        item=ExportItem(path=[PathNode(name='opened_by')]),
        help_text=_("The id of the user who opened the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='opened_by_username',
        item=ExportItem(path=[PathNode(name='opened_by')]),
        help_text=_("The username of the user who opened the case"),
        transforms=[USERNAME_TRANSFORM],
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='opened_date',
        item=ExportItem(path=[PathNode(name='opened_on')]),
        help_text=_("The date and time at which the case was opened"),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='owner_id',
        item=ExportItem(path=[PathNode(name='owner_id')]),
        help_text=_("The id of the user who owns the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='owner_name',
        item=ExportItem(path=[PathNode(name='owner_id')]),
        help_text=_("The username of the user who owns the case"),
        transforms=[USERNAME_TRANSFORM],
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='server_last_modified_date',
        item=ExportItem(path=[PathNode(name='server_modified_on')]),
        help_text=_("The date and time at which the server received the form that last modified the case"),
        transforms=[USERNAME_TRANSFORM],
        is_advanced=True,
    ),
    # TODO: Make sure state gets converted to a doc_type or whatever in the form es index
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label='state',
        item=ExportItem(path=[PathNode(name='doc_type')]),
        is_advanced=True,
    ),
]
MAIN_CASE_TABLE_PROPERTIES = TOP_MAIN_CASE_TABLE_PROPERTIES + BOTTOM_MAIN_FORM_TABLE_PROPERTIES

CASE_HISTORY_PROPERTIES = [
    ExportColumn(
        tags=[PROPERTY_TAG_ROW],
        label='number',
        item=ExportItem(path=[PathNode(name='number')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='action_type',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='action_type')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='user_id',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='user_id')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='date',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='date')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='server_date',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='server_date')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='xform_id',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='xform_id')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='xform_xmlns',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='xform_xmlns')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='xform_name',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='xform_name')]),    
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='deprecated',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='deprecated')]),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='sync_log_id',
        item=ExportItem(path=[PathNode(name='actions', is_repeat=True), PathNode(name='sync_log_id')]),
        is_advanced=True,
    ),
]

PARENT_CASE_TABLE_PROPERTIES = [
    ExportColumn(
        tags=[PROPERTY_TAG_ROW],
        label='number',
        item=ExportItem(path=[PathNode(name='number')]),
        is_advanced=False
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='parent_case_id',
        item=ExportItem(path=[PathNode(name='indices', is_repeat=True), PathNode(name='referenced_id')]),
        is_advanced=False
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='parent_case_type',
        item=ExportItem(path=[PathNode(name='indices', is_repeat=True), PathNode(name='referenced_type')]),
        is_advanced=False
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_NONE],
        label='relationship_type',
        item=ExportItem(path=[PathNode(name='indices', is_repeat=True), PathNode(name='relationship')]),
        is_advanced=False
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label='state',
        item=ExportItem(path=[PathNode(name='indices', is_repeat=True), PathNode(name='doc_type')]),
        is_advanced=False
    ),
]
