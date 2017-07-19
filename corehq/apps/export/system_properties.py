from django.utils.translation import ugettext_noop as _

from corehq.apps.export.const import (
    PROPERTY_TAG_ROW,
    PROPERTY_TAG_INFO,
    PROPERTY_TAG_APP,
    PROPERTY_TAG_SERVER,
    PROPERTY_TAG_CASE,
    PROPERTY_TAG_STOCK,
    CASE_NAME_TRANSFORM,
    CASE_OR_USER_ID_TRANSFORM,
    DOC_TYPE_TRANSFORM,
    OWNER_ID_TRANSFORM,
    USERNAME_TRANSFORM,
    WORKFLOW_TRANSFORM,
    PROPERTY_TAG_NONE
)
from corehq.apps.export.models import (
    ExportColumn,
    ExportItem,
    PathNode,
    StockExportColumn,
    RowNumberColumn,
    SplitGPSExportColumn,
    GeopointItem,
)

# System properties to be displayed above the form questions
TOP_MAIN_FORM_TABLE_PROPERTIES = [
    RowNumberColumn(
        tags=[PROPERTY_TAG_ROW],
        label="number",
        item=ExportItem(path=[PathNode(name='number')]),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label="formid",
        item=ExportItem(path=[
            PathNode(name='form'),
            PathNode(name='meta'),
            PathNode(name='instanceID')
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
        label='started_time',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='timeStart')
        ]),
        help_text=_('The time at which this form was started'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='username',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='username')
        ]),
        help_text=_('The username of the user who submitted this form'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='userID',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')
        ]),
        is_advanced=True,
        help_text=_("The ID of the user who submitted this form")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='@xmlns',
        item=ExportItem(path=[PathNode(name='xmlns')]),
        is_advanced=True,
        help_text=_('The XMLNS of this form')
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
        help_text=_('The version of CommCare and the app that was used to submit this form')),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='deviceID',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='deviceID')
        ]),
        is_advanced=True,
        help_text=_("The ID of the device that submitted this form")
    ),
    SplitGPSExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='location',
        item=GeopointItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='location')
        ]),
        is_advanced=True,
        help_text=_("GPS capture when opening the form"),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='app_id',
        item=ExportItem(path=[PathNode(name='app_id')]),
        is_advanced=True,
        help_text=_("The ID of the app that this form is part of")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='build_id',
        item=ExportItem(path=[PathNode(name='build_id')]),
        is_advanced=True,
        help_text=_("The ID of the published app that this form is part of")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='@version',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='@version')
        ]),
        is_advanced=True,
        help_text=_("The version of the app in which this form was last updated prior to being published")
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
        help_text=_("The ID of the last sync on the phone that occurred prior to submitting this form.")
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
        label="edited_on",
        item=ExportItem(path=[PathNode(name="edited_on")]),
        is_advanced=True,
        help_text=_("The time at which this form was last edited."),
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
        help_text=_('The ID of the case that this form operated on')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='case_name',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='case'), PathNode(name='@case_id')
        ], transform=CASE_NAME_TRANSFORM),
        selected=True,
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
        help_text=_('The owner ID of the case that this form opened')
    ),
]
MAIN_FORM_TABLE_PROPERTIES = TOP_MAIN_FORM_TABLE_PROPERTIES + BOTTOM_MAIN_FORM_TABLE_PROPERTIES

ROW_NUMBER_COLUMN = RowNumberColumn(
    tags=[PROPERTY_TAG_ROW],
    label='number',
    item=ExportItem(path=[PathNode(name='number')]),
)

STOCK_COLUMN = StockExportColumn(
    tags=[PROPERTY_TAG_STOCK],
    label='stock',
    item=ExportItem(path=[PathNode(name='stock')]),
    help_text=_('Add stock data columns to the export'),
)

TOP_MAIN_CASE_TABLE_PROPERTIES = [
    # This first list is displayed above the case properties
    RowNumberColumn(
        tags=[PROPERTY_TAG_ROW],
        label='number',
        item=ExportItem(path=[PathNode(name='number')]),
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='caseid',
        item=ExportItem(path=[PathNode(name='_id')]),
        help_text=_("The ID of the case"),
        selected=True
    ),
    ExportColumn(
        label='name',
        item=ExportItem(path=[PathNode(name='name')]),
        help_text=_("The name of the case"),
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
        help_text=_("The ID of the user who closed the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='closed_by_username',
        item=ExportItem(path=[PathNode(name='closed_by')], transform=USERNAME_TRANSFORM),
        help_text=_("The username of the user who closed the case"),
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
        help_text=_("The external ID for this case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='last_modified_by_user_id',
        item=ExportItem(path=[PathNode(name='user_id')]),
        help_text=_("The ID of the user who last modified this case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='last_modified_by_user_username',
        item=ExportItem(path=[PathNode(name='user_id')], transform=USERNAME_TRANSFORM),
        help_text=_("The username of the user who last modified this case"),
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
        help_text=_("The ID of the user who opened the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='opened_by_username',
        item=ExportItem(path=[PathNode(name='opened_by')], transform=USERNAME_TRANSFORM),
        help_text=_("The username of the user who opened the case"),
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
        help_text=_("The ID of the user who owns the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='owner_name',
        item=ExportItem(path=[PathNode(name='owner_id')], transform=OWNER_ID_TRANSFORM),
        help_text=_("The username of the user who owns the case"),
        selected=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='server_last_modified_date',
        item=ExportItem(path=[PathNode(name='server_modified_on')], transform=USERNAME_TRANSFORM),
        help_text=_("The date and time at which the server received the form that last modified the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label='state',
        item=ExportItem(path=[PathNode(name='doc_type')]),
        is_advanced=True,
    ),
]
MAIN_CASE_TABLE_PROPERTIES = TOP_MAIN_CASE_TABLE_PROPERTIES + BOTTOM_MAIN_CASE_TABLE_PROPERTIES

CASE_HISTORY_PROPERTIES = [
    RowNumberColumn(
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
    RowNumberColumn(
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

_SMS_COLUMNS = [
    ("Contact Type", "couch_recipient_doc_type", DOC_TYPE_TRANSFORM),
    ("Contact ID", "couch_recipient", None),
    ("Timestamp", "date", None),
    ("User Name", "couch_recipient", CASE_OR_USER_ID_TRANSFORM),
    ("Phone Number", "phone_number", None),
    ("Direction", "direction", None),
    ("Message", "text", None),
    ("Type", "workflow", WORKFLOW_TRANSFORM),
]

SMS_TABLE_PROPERTIES = [
    RowNumberColumn(
        tags=[PROPERTY_TAG_ROW],
        label='number',
        item=ExportItem(path=[PathNode(name='number')]),
        is_advanced=False
    )
] + [
    ExportColumn(
        label=col[0],
        item=ExportItem(
            path=[PathNode(name=col[1])],
            transform=col[2]
        ),
        selected=True
    )
    for col in _SMS_COLUMNS
]
