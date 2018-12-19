from __future__ import absolute_import
from __future__ import unicode_literals
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
    PROPERTY_TAG_NONE,
    CASE_ID_TO_LINK,
    FORM_ID_TO_LINK,
)
from corehq.apps.export.models import (
    ExportColumn,
    ExportItem,
    PathNode,
    StockExportColumn,
    RowNumberColumn,
    SplitGPSExportColumn,
    GeopointItem,
    ScalarItem,
)

# System properties to be displayed above the form questions
from corehq.apps.userreports.datatypes import DATA_TYPE_DATETIME, DATA_TYPE_STRING

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
        item=ExportItem(
            path=[PathNode(name='form'), PathNode(name='meta'), PathNode(name='timeEnd')],
            datatype=DATA_TYPE_DATETIME,
        ),
        help_text=_('The time at which this form was completed'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='started_time',
        item=ExportItem(
            path=[PathNode(name='form'), PathNode(name='meta'), PathNode(name='timeStart')],
            datatype=DATA_TYPE_DATETIME,
        ),
        help_text=_('The time at which this form was started'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='username',
        item=ExportItem(
            path=[PathNode(name='form'), PathNode(name='meta'), PathNode(name='username')],
            datatype=DATA_TYPE_STRING,
        ),
        help_text=_('The username of the user who submitted this form'),
        selected=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='userID',
        item=ExportItem(
            path=[PathNode(name='form'), PathNode(name='meta'), PathNode(name='userID')],
            datatype=DATA_TYPE_STRING,
        ),
        is_advanced=True,
        help_text=_("The ID of the user who submitted this form")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='@xmlns',
        item=ExportItem(path=[PathNode(name='xmlns')], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_('The XMLNS of this form')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='@name',
        item=ExportItem(path=[PathNode(name='form'), PathNode(name='@name')], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_('The name of this form')
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='App Version',
        item=ExportItem(path=[
            PathNode(name='form'), PathNode(name='meta'), PathNode(name='appVersion', datatype=DATA_TYPE_STRING)
        ]),
        is_advanced=True,
        help_text=_('The version of CommCare and the app that was used to submit this form')),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='deviceID',
        item=ExportItem(
            path=[PathNode(name='form'), PathNode(name='meta'), PathNode(name='deviceID')],
            datatype=DATA_TYPE_STRING,
        ),
        is_advanced=True,
        help_text=_("The ID of the device that submitted this form")
    ),
    SplitGPSExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='location',
        item=GeopointItem(
            path=[PathNode(name='form'), PathNode(name='meta'), PathNode(name='location')],
            datatype=DATA_TYPE_STRING,
        ),
        is_advanced=True,
        help_text=_("GPS capture when opening the form"),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='app_id',
        item=ExportItem(path=[PathNode(name='app_id')], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_("The ID of the app that this form is part of")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='build_id',
        item=ExportItem(path=[PathNode(name='build_id')], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_("The ID of the published app that this form is part of")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_APP],
        label='@version',
        item=ExportItem(
            path=[PathNode(name='form'), PathNode(name='@version')],
            datatype=DATA_TYPE_STRING,
        ),
        is_advanced=True,
        help_text=_("The version of the app in which this form was last updated prior to being published")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="state",
        item=ExportItem(path=[PathNode(name="doc_type")], datatype=DATA_TYPE_STRING),
        is_advanced=True
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="last_sync_token",
        item=ExportItem(path=[PathNode(name="last_sync_token")], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_("The ID of the last sync on the phone that occurred prior to submitting this form.")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="partial_submission",
        item=ExportItem(path=[PathNode(name="partial_submission")], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_("True if the form was a partial submission, False otherwise.")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="received_on",
        item=ExportItem(path=[PathNode(name="received_on")], datatype=DATA_TYPE_DATETIME),
        selected=True,
        help_text=_("The time at which the server receive this form submission"),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="edited_on",
        item=ExportItem(path=[PathNode(name="edited_on")], datatype=DATA_TYPE_DATETIME),
        is_advanced=True,
        help_text=_("The time at which this form was last edited."),
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label="submit_ip",
        item=ExportItem(path=[PathNode(name="submit_ip")], datatype=DATA_TYPE_STRING),
        is_advanced=True,
        help_text=_("The IP address from which the form was submitted")
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label="form_link",
        item=ExportItem(
            path=[
                PathNode(name='form'),
                PathNode(name='meta'),
                PathNode(name='instanceID')
            ],
            transform=FORM_ID_TO_LINK,
        ),
        help_text=_('Link to this form'),
        selected=True,
    ),
]
MAIN_FORM_TABLE_PROPERTIES = TOP_MAIN_FORM_TABLE_PROPERTIES + BOTTOM_MAIN_FORM_TABLE_PROPERTIES


def get_case_name_column(case_id_export_item):
    label_segments = case_id_export_item.readable_path.split('.')[:-1]
    label_segments.append('case_name')
    return ExportColumn(
        tags=[PROPERTY_TAG_CASE],
        label='.'.join(label_segments),
        item=ExportItem(path=case_id_export_item.path, transform=CASE_NAME_TRANSFORM),
        selected=False,
        is_advanced=True,
        help_text=_("The name of the case that this form operated on")
    )

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
        item=ScalarItem(path=[PathNode(name='name')]),
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
        item=ExportItem(path=[PathNode(name='closed_on')], datatype=DATA_TYPE_DATETIME),
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
        item=ExportItem(path=[PathNode(name='modified_on')], datatype=DATA_TYPE_DATETIME),
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
        item=ExportItem(path=[PathNode(name='opened_on')], datatype=DATA_TYPE_DATETIME),
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
        item=ExportItem(path=[PathNode(name='server_modified_on')], datatype=DATA_TYPE_DATETIME),
        help_text=_("The date and time at which the server received the form that last modified the case"),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_SERVER],
        label='state',
        item=ExportItem(path=[PathNode(name='doc_type')]),
        is_advanced=True,
    ),
    ExportColumn(
        tags=[PROPERTY_TAG_INFO],
        label='case_link',
        item=ExportItem(path=[PathNode(name='_id')], transform=CASE_ID_TO_LINK),
        help_text=_("Link to this case"),
        selected=True
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
