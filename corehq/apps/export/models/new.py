import logging
from collections import OrderedDict, defaultdict, namedtuple
from copy import copy
from datetime import datetime
from functools import partial
from itertools import groupby

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.http import Http404
from django.utils.datastructures import OrderedSet
from django.utils.translation import gettext as _

from couchdbkit import (
    BooleanProperty,
    DictProperty,
    ResourceConflict,
    SchemaListProperty,
    SchemaProperty,
)
from jsonobject.exceptions import BadValueError
from memoized import memoized

from casexml.apps.case.const import DEFAULT_CASE_INDEX_IDENTIFIERS
from couchexport.models import Format
from couchexport.transforms import couch_to_excel_datetime
from dimagi.ext.couchdbkit import (
    DateProperty,
    DateTimeProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    ListProperty,
    SetProperty,
    StringProperty,
)
from dimagi.utils.couch.database import iter_docs
from soil.progress import set_task_progress

from corehq import feature_previews
from corehq.apps.app_manager.app_schemas.case_properties import (
    ParentCasePropertyBuilder,
)
from corehq.apps.app_manager.const import STOCK_QUESTION_TAG_NAMES
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_app_ids_in_domain,
    get_built_app_ids_with_submissions_for_app_id,
    get_built_app_ids_with_submissions_for_app_ids_and_versions,
    get_latest_app_ids_and_versions,
)
from corehq.apps.app_manager.models import (
    AdvancedFormActions,
    Application,
    CaseIndex,
    OpenSubCaseAction,
    RemoteApp,
)
from corehq.apps.domain.models import Domain
from corehq.apps.export.const import (
    ALL_CASE_TYPE_EXPORT,
    CASE_ATTRIBUTES,
    CASE_CLOSE_TO_BOOLEAN,
    CASE_CREATE_ELEMENTS,
    CASE_DATA_SCHEMA_VERSION,
    CASE_EXPORT,
    CASE_ID_TO_LINK,
    CASE_NAME_TRANSFORM,
    DEID_TRANSFORM_FUNCTIONS,
    EMPTY_VALUE,
    EXCEL_MAX_SHEET_NAME_LENGTH,
    FORM_DATA_SCHEMA_VERSION,
    FORM_EXPORT,
    FORM_ID_TO_LINK,
    KNOWN_CASE_PROPERTIES,
    MISSING_VALUE,
    PLAIN_USER_DEFINED_SPLIT_TYPE,
    PROPERTY_TAG_CASE,
    PROPERTY_TAG_DELETED,
    PROPERTY_TAG_UPDATE,
    SMS_DATA_SCHEMA_VERSION,
    SMS_EXPORT,
    TRANSFORM_FUNCTIONS,
    UNKNOWN_INFERRED_FROM,
    USER_DEFINED_SPLIT_TYPES,
    SharingOption,
)
from corehq.apps.export.dbaccessors import (
    get_case_inferred_schema,
    get_form_inferred_schema,
    get_latest_case_export_schema,
    get_latest_form_export_schema,
)
from corehq.apps.export.esaccessors import (
    get_case_export_base_query,
    get_form_export_base_query,
    get_sms_export_base_query,
)
from corehq.apps.export.utils import is_occurrence_deleted
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.daterange import get_daterange_start_end_dates
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.models import HQUserType
from corehq.apps.userreports.app_manager.data_source_meta import (
    get_form_indicator_data_type,
)
from corehq.apps.userreports.expressions.getters import NestedDictGetter
from corehq.blobs import CODES, get_blob_db
from corehq.blobs.exceptions import NotFound
from corehq.blobs.mixin import BlobMixin
from corehq.blobs.models import BlobMeta
from corehq.blobs.util import random_url_id
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.util.global_request import get_request_domain
from corehq.util.html_utils import strip_tags
from corehq.util.timezones.utils import get_timezone_for_domain
from corehq.util.view_utils import absolute_reverse
from corehq.apps.data_dictionary.util import (
    get_data_dict_props_by_case_type,
    get_deprecated_fields,
)
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain
from corehq.apps.userreports.util import get_indicator_adapter


DAILY_SAVED_EXPORT_ATTACHMENT_NAME = "payload"


ExcelFormatValue = namedtuple('ExcelFormatValue', 'format value')


class PathNode(DocumentSchema):
    """
    A PathNode represents a portion of a path to value in a document.

    For example, if a document looked like:

    {
        'form': {
            'question': 'one'
        }

    }

    A path to the data 'one' would be ['form']['question']. A PathNode represents
    one step in that path. In this example, a list of PathNodes would represent
    fetching the 'one':

    [PathNode(name='form'), PathNode(name='question')]
    """

    name = StringProperty(required=True)

    # This is true if this step in the path corresponds with an array (such as a repeat group)
    is_repeat = BooleanProperty(default=False)

    def __key(self):
        return (type(self), self.doc_type, self.name, self.is_repeat)

    def __eq__(self, other):
        # First we try a least expensive comparison (name vs name) to rule the
        # majority of failed comparisons. This improves performance by nearly
        # a factor of 2 when __eq__ is used on large data sets.
        if self.name == other.name:
            return self.__key() == other.__key()
        return False

    def __hash__(self):
        return hash(self.__key())


class ReadablePathMixin(object):
    @property
    def readable_path(self):
        return '.'.join([node.name for node in self.path])


class ExportItem(DocumentSchema, ReadablePathMixin):
    """
    An item for export.
    path: A question path like [PathNode(name=("my_group"), PathNode(name="q1")]
        or a case property name like [PathNode(name="date_of_birth")].
    label: The label of the corresponding form question, or the case property name
    tag: Denotes whether the property is a system, meta, etc
    last_occurrences: A dictionary that maps an app_id to the last version the export item was present
    """
    path = SchemaListProperty(PathNode)
    label = StringProperty()
    tag = StringProperty()
    last_occurrences = DictProperty()
    transform = StringProperty(choices=list(TRANSFORM_FUNCTIONS))
    # this is not used by exports, but other things that use this schema (e.g. app-based UCRs)
    datatype = StringProperty()

    # True if this item was inferred from different actions in HQ (i.e. case upload)
    # False if the item was found in the application structure
    inferred = BooleanProperty(default=False)
    inferred_from = SetProperty(default=set)

    def __key(self):
        return '{}:{}:{}'.format(
            _path_nodes_to_string(self.path),
            self.doc_type,
            self.transform,
        )

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    @classmethod
    def wrap(cls, data):
        if cls is ExportItem:
            doc_type = data['doc_type']
            if doc_type == 'ExportItem':
                return super(ExportItem, cls).wrap(data)
            elif doc_type == 'ScalarItem':
                return ScalarItem.wrap(data)
            elif doc_type == 'LabelItem':
                return LabelItem.wrap(data)
            elif doc_type == 'MultipleChoiceItem':
                return MultipleChoiceItem.wrap(data)
            elif doc_type == 'GeopointItem':
                return GeopointItem.wrap(data)
            elif doc_type == 'CaseIndexItem':
                return CaseIndexItem.wrap(data)
            elif doc_type == 'MultiMediaItem':
                return MultiMediaItem.wrap(data)
            elif doc_type == 'StockItem':
                return StockItem.wrap(data)
            else:
                raise ValueError('Unexpected doc_type for export item', doc_type)
        else:
            return super(ExportItem, cls).wrap(data)

    @classmethod
    def create_from_question(cls, question, app_id, app_version, repeats):
        return cls(
            path=_question_path_to_path_nodes(question['value'], repeats),
            label=strip_tags(question['label']),
            last_occurrences={app_id: app_version},
            datatype=get_form_indicator_data_type(question['type'])
        )

    @classmethod
    def merge(cls, one, two):
        item = one
        item.label = two.label  # always take the newest label
        item.last_occurrences = _merge_dicts(one.last_occurrences, two.last_occurrences)
        item.inferred = one.inferred or two.inferred
        item.inferred_from |= two.inferred_from
        return item


class ExportColumn(DocumentSchema):
    """
    The model that represents a column in an export. Each column has a one-to-one
    mapping with an ExportItem. The column controls the presentation of that item.
    """

    item = SchemaProperty(ExportItem)
    label = StringProperty()
    # Determines whether or not to show the column in the UI Config without clicking advanced
    is_advanced = BooleanProperty(default=False)
    is_deleted = BooleanProperty(default=False)
    is_deprecated = BooleanProperty(default=False)
    selected = BooleanProperty(default=False)
    tags = ListProperty()
    help_text = StringProperty()

    # A transforms that deidentifies the value
    deid_transform = StringProperty(choices=list(DEID_TRANSFORM_FUNCTIONS))

    def get_value(self, domain, doc_id, doc, base_path, transform_dates=False, row_index=None, split_column=False):
        """
        Get the value of self.item of the given doc.
        When base_path is [], doc is a form submission or case,
        when base_path is non empty, doc is a repeat group from a form submission.
        :param domain: Domain that the document belongs to
        :param doc_id: The form submission or case id
        :param doc: A form submission or instance of a repeat group in a submission or case
        :param base_path: The PathNode list to the column
        :param transform_dates: If set to True, will convert dates to be compatible with Excel
        :param row_index: This is used for the RowExportColumn to determine what index the row is on
        :param split_column: When True will split SplitExportColumn into multiple columns, when False, it will
            not split the column
        :return:
        """
        assert base_path == self.item.path[:len(base_path)], "ExportItem's path doesn't start with the base_path"
        # Get the path from the doc root to the desired ExportItem
        path = [x.name for x in self.item.path[len(base_path):]]
        return self._transform(NestedDictGetter(path)(doc), doc, transform_dates)

    def _transform(self, value, doc, transform_dates):
        """
        Transform the given value with the transform specified in self.item.transform.
        Also transform dates if the transform_dates flag is true.
        """

        # When XML elements have additional attributes in them, the text node is
        # put inside of the #text key. For example:
        #
        # <element id="123">value</element>  -> {'#text': 'value', 'id':'123'}
        #
        # Whereas elements without additional attributes just take on the string value:
        #
        # <element>value</element>  -> 'value'
        #
        # This line ensures that we grab the actual value instead of the dictionary
        if isinstance(value, dict):
            if '#text' in value:
                value = value.get('#text')
            else:
                return EMPTY_VALUE

        if transform_dates:
            value = couch_to_excel_datetime(value, doc)
        if self.item.transform:
            value = TRANSFORM_FUNCTIONS[self.item.transform](value, doc)
        if self.deid_transform:
            try:
                value = DEID_TRANSFORM_FUNCTIONS[self.deid_transform](value, doc)
            except ValueError:
                # Unable to convert the string to a date
                pass
        if value is None:
            value = MISSING_VALUE

        if isinstance(value, list):
            def _serialize(str_or_dict):
                """
                Serialize old data for scalar questions that were previously a repeat

                This is a total edge case. See https://manage.dimagi.com/default.asp?280549.
                """
                if isinstance(str_or_dict, dict):
                    return ','.join('{}={}'.format(k, v) for k, v in str_or_dict.items())
                else:
                    return str_or_dict

            value = ' '.join(_serialize(elem) for elem in value)
        return value

    @staticmethod
    def create_default_from_export_item(
        table_path,
        item,
        app_ids_and_versions,
        auto_select=True,
        is_deprecated=False
    ):
        """Creates a default ExportColumn given an item

        :param table_path: The path of the table_path that the item belongs to
        :param item: An ExportItem instance
        :param app_ids_and_versions: A dictionary of app ids that map to latest build version
        :param auto_select: Automatically select the column
        :param is_deprecated: Whether the property has been deprecated in the data dictionary
        :returns: An ExportColumn instance
        """
        is_case_update = item.tag == PROPERTY_TAG_CASE and not isinstance(item, CaseIndexItem)
        is_case_id = is_case_update and item.path[-1].name == '@case_id'
        is_case_history_update = item.tag == PROPERTY_TAG_UPDATE
        is_label_question = isinstance(item, LabelItem)

        is_main_table = table_path == MAIN_TABLE
        is_bulk_export = (ALL_CASE_TYPE_TABLE in table_path)
        constructor_args = {
            "item": item,
            "label": item.readable_path if not is_case_history_update else item.label,
            "is_advanced": not is_case_id and (is_case_update or is_label_question),
            "is_deprecated": is_deprecated
        }

        if isinstance(item, GeopointItem):
            column = SplitGPSExportColumn(**constructor_args)
        elif isinstance(item, MultiMediaItem):
            column = MultiMediaExportColumn(**constructor_args)
        elif isinstance(item, StockItem):
            column = StockFormExportColumn(**constructor_args)
        elif isinstance(item, MultipleChoiceItem):
            column = SplitExportColumn(**constructor_args)
        elif isinstance(item, CaseIndexItem):
            column = CaseIndexExportColumn(
                help_text=_('The ID of the associated {} case type').format(item.case_type),
                **constructor_args
            )
        elif get_request_domain() and feature_previews.SPLIT_MULTISELECT_CASE_EXPORT.enabled(get_request_domain()):
            column = SplitUserDefinedExportColumn(**constructor_args)
        else:
            column = ExportColumn(**constructor_args)
        column.update_properties_from_app_ids_and_versions(app_ids_and_versions)
        column.selected = (
            auto_select
            and not column._is_deleted(app_ids_and_versions)
            and (not is_case_update or is_case_id)
            and not is_label_question
            and (is_main_table or is_bulk_export)
            and not is_deprecated
        )
        return column

    def _is_deleted(self, app_ids_and_versions):
        return (
            is_occurrence_deleted(self.item.last_occurrences, app_ids_and_versions)
            and not self.item.inferred
        )

    def update_properties_from_app_ids_and_versions(self, app_ids_and_versions):
        """
        This regenerates properties based on new build ids/versions
        :param app_ids_and_versions: A dictionary of app ids that map to latest build version
        most recent state of the app(s) in the domain
        """
        self.is_deleted = self._is_deleted(app_ids_and_versions)

        tags = []
        if self.is_deleted:
            tags.append(PROPERTY_TAG_DELETED)

        if self.item.tag:
            tags.append(self.item.tag)
        self.is_advanced = self.is_advanced
        self.tags = tags

    @property
    def is_deidentifed(self):
        return bool(self.deid_transform)

    def get_headers(self, split_column=False):
        if self.is_deidentifed:
            return [f"{self.label} *sensitive*"]
        else:
            return [self.label]

    @classmethod
    def wrap(cls, data):
        if cls is ExportColumn:
            doc_type = data['doc_type']
            if doc_type == 'ExportColumn':
                return super(ExportColumn, cls).wrap(data)
            elif doc_type == 'SplitExportColumn':
                return SplitExportColumn.wrap(data)
            elif doc_type == 'RowNumberColumn':
                return RowNumberColumn.wrap(data)
            elif doc_type == 'StockExportColumn':
                return StockExportColumn.wrap(data)
            elif doc_type == 'CaseIndexExportColumn':
                return CaseIndexExportColumn.wrap(data)
            elif doc_type == 'SplitUserDefinedExportColumn':
                return SplitUserDefinedExportColumn.wrap(data)
            elif doc_type == 'UserDefinedExportColumn':
                return UserDefinedExportColumn.wrap(data)
            elif doc_type == 'SplitGPSExportColumn':
                return SplitGPSExportColumn.wrap(data)
            elif doc_type == 'MultiMediaExportColumn':
                return MultiMediaExportColumn.wrap(data)
            elif doc_type == 'StockFormExportColumn':
                return StockFormExportColumn.wrap(data)
            else:
                raise ValueError('Unexpected doc_type for export column', doc_type)
        else:
            return super(ExportColumn, cls).wrap(data)


class DocRow(namedtuple("DocRow", ["doc", "row"])):
    """
    DocRow represents a document and its row index.
    doc - doc is a dictionary representing a form or a subset of a form (like
          a particular iteration of a repeat group)
    row - row is a tuple representing the relationship between this doc and the
          rows in other sheets. For example, if this doc represents the 3rd
          iteration of a repeat group in the 1st form of the export, then this
          DocRow would have a row of (0, 2).
    """


class TableConfiguration(DocumentSchema, ReadablePathMixin):
    """
    The TableConfiguration represents one excel sheet in an export.
    It contains a list of columns and other presentation properties
    """
    # label saves the user's decision for the table name
    label = StringProperty()
    path = ListProperty(PathNode)
    columns = ListProperty(ExportColumn)
    selected = BooleanProperty(default=False)
    is_deleted = BooleanProperty(default=False)
    is_user_defined = BooleanProperty(default=False)

    def __hash__(self):
        return hash(tuple(self.path))

    @property
    def selected_columns(self):
        """The columns that should be included in the export"""
        return [c for c in self.columns if c.selected]

    def get_headers(self, split_columns=False):
        """
        Return a list of column headers
        """
        headers = []
        for column in self.selected_columns:
            headers.extend(column.get_headers(split_column=split_columns))
        return headers

    def get_rows(self, document, row_number, split_columns=False,
                 transform_dates=False, as_json=False, include_hyperlinks=True):
        """
        Return a list of ExportRows generated for the given document.
        :param document: dictionary representation of a form submission or case
        :param row_number: number indicating this documents index in the sequence of all documents in the export
        :param as_json: optional parameter, mainly used in APIs, to spit out
                        the data as a json-ready dict
        :param include_hyperlinks: optional parameter, if True will specify
                                   which column indices to hyperlink
        :return: List of ExportRows
        """
        document_id = document.get('_id')

        sub_documents = self._get_sub_documents(document, row_number, document_id=document_id)

        domain = document.get('domain')

        assert domain is not None, 'Form or Case must be associated with domain'
        assert document_id is not None, 'Form or Case must have an id'

        rows = []
        for doc_row in sub_documents:
            doc, row_index = doc_row.doc, doc_row.row

            row_data = {} if as_json else []
            col_index = 0
            skip_excel_formatting = []
            for col in self.selected_columns:
                # When doing a bulk case export, each column will have a reference to the ALL_CASE_TYPE_EXPORT
                # case type in its path. This needs to be temporarily removed when getting the value.
                base_path = self.path
                if ALL_CASE_TYPE_TABLE in base_path:
                    base_path = []

                val = col.get_value(
                    domain,
                    document_id,
                    doc,
                    base_path,
                    row_index=row_index,
                    split_column=split_columns,
                    transform_dates=transform_dates,
                )
                if as_json:
                    for index, header in enumerate(col.get_headers(split_column=split_columns)):
                        if isinstance(val, list):
                            row_data[header] = "{}".format(val[index])
                        else:
                            row_data[header] = "{}".format(val)
                elif isinstance(val, list):
                    row_data.extend(val)

                    # we never want to auto-format RowNumberColumn
                    # (always treat as text)
                    next_col_index = col_index + len(val)
                    if isinstance(col, RowNumberColumn):
                        skip_excel_formatting.extend(
                            list(range(col_index, next_col_index))
                        )
                    col_index = next_col_index
                else:
                    row_data.append(val)

                    # we never want to auto-format RowNumberColumn
                    # (always treat as text)
                    if isinstance(col, RowNumberColumn):
                        skip_excel_formatting.append(col_index)
                    col_index += 1
            if as_json:
                rows.append(row_data)
            else:
                hyperlink_indices = self.get_hyperlink_column_indices(
                    split_columns) if include_hyperlinks else []
                rows.append(ExportRow(
                    data=row_data,
                    hyperlink_column_indices=hyperlink_indices,
                    skip_excel_formatting=skip_excel_formatting
                ))
        return rows

    @staticmethod
    def _create_index(_path, _transform):
        return f'{_path_nodes_to_string(_path)} t.{_transform}'

    def _regenerate_column_cache(self):
        self._string_column_paths = [
            self._create_index(column.item.path, column.item.transform)
            for column in self.columns
        ]

    def get_column(self, item_path, item_doc_type, column_transform):
        """
        Given a path and transform, will return the column and its index. If not found, will
        return None, None.

        :param item_path: A list of path nodes that identify a column
        :param item_doc_type: The doc type of the item (often just ExportItem). If getting
                UserDefinedExportColumn, set this to None
        :param column_transform: A transform that is applied on the column
        :returns index, column: The index of the column in the list and an ExportColumn
        """

        string_item_path = self._create_index(item_path, column_transform)

        # Previously we iterated over self.columns with each call to return the
        # index. Now we do an index lookup on the string-ified path names for
        # self.columns and regenerate it only when the length of self.columns
        # changes. This happens frequently when the table is being constructed.
        if (not hasattr(self, '_string_column_paths')
                or len(self._string_column_paths) != len(self.columns)):
            self._regenerate_column_cache()

        # While unlikely, it is possible for the same path to be used for multiple items.
        # This can occur, for example, when a new reserved case property is introduced.
        # In this case, the reserved property will be an 'ExportItem', while a user-defined
        #  case property would be a 'ScalarItem'.
        # If we can ensure that paths are one-to-one with items, this can be removed in the future.
        indices = [index for (index, path) in enumerate(self._string_column_paths) if path == string_item_path]
        for index in indices:
            column = self.columns[index]

            # The column cache can currently get out of sync because other code directly modifies
            # the columns. For example, ExportInstance._move_selected_columns_to_top just completely
            # overwrites column order without updating our cache.
            # TODO: Modify code such that all table manipulation is done through this class
            if column.item.path != item_path:
                self._regenerate_column_cache()
                index = self._string_column_paths.index(string_item_path)
                column = self.columns[index]

            # Despite the column being found based on a key containing the item_path and transform,
            # both still need to be checked here to prevent the edge case where the the path or the transform
            # contain formatting that makes them blend together.
            if (column.item.path == item_path
                    and column.item.transform == column_transform
                    and column.item.doc_type == item_doc_type):
                return index, column
            elif (isinstance(column, UserDefinedExportColumn)
                    and column.custom_path == item_path
                    and item_doc_type is None):
                return index, column

        return None, None

    @memoized
    def get_hyperlink_column_indices(self, split_columns):
        export_column_index = 0
        hyperlink_column_indices = []
        for selected_column in self.selected_columns:
            if selected_column.item.transform in [CASE_ID_TO_LINK, FORM_ID_TO_LINK]:
                hyperlink_column_indices.append(export_column_index)
            export_column_index += len(selected_column.get_headers(split_column=split_columns))
        return hyperlink_column_indices

    def _get_sub_documents(self, document, row_number, document_id=None):
        return self._get_sub_documents_helper(document_id, self.path,
                                              [DocRow(row=(row_number,), doc=document)])

    @staticmethod
    def _get_sub_documents_helper(document_id, path, row_docs):
        """
        Return each instance of a repeat group at the path from the given docs.
        If path is [], just return the docs

        See corehq.apps.export.tests.test_table_configuration.TableConfigurationGetRowsTest.test_get_sub_documents
        for examples

        :param path: A list of a strings
        :param docs: A list of dicts representing form submissions
        :return:
        """
        if len(path) == 0 or ALL_CASE_TYPE_TABLE in path:
            return row_docs

        new_docs = []
        for row_doc in row_docs:
            doc = row_doc.doc
            row_index = row_doc.row
            path_name = path[0].name

            if isinstance(doc, dict):
                next_doc = doc.get(path_name, {})
            else:
                next_doc = {}
            if path[0].is_repeat:
                if not isinstance(next_doc, list):
                    # This happens when a repeat group has a single repeat iteration
                    next_doc = [next_doc]
                new_docs.extend([
                    DocRow(row=row_index + (new_doc_index,), doc=new_doc)
                    for new_doc_index, new_doc in enumerate(next_doc)
                ])
            elif next_doc:
                new_docs.append(DocRow(row=row_index, doc=next_doc))
        return TableConfiguration._get_sub_documents_helper(document_id, path[1:], new_docs)


class DatePeriod(DocumentSchema):
    period_type = StringProperty(required=True)
    days = IntegerProperty()
    begin = DateProperty()
    end = DateProperty()

    @property
    def startdate(self):
        startdate, _ = get_daterange_start_end_dates(self.period_type, self.begin, self.end, self.days)
        return startdate

    @property
    def enddate(self):
        _, enddate = get_daterange_start_end_dates(self.period_type, self.begin, self.end, self.days)
        return enddate


class ExportInstanceFilters(DocumentSchema):
    """
    A class represented a saved set of filters for an export
    These are used for Daily Saved Exports, and Dashboard Feeds (which are a type of Daily Saved Export)
    """
    # accessible_location_ids is a list of ids that the creator of the report (and thereby creator of the filters
    # as well) has access to. locations is a list of ids that the user has selected in the filter UI. The user
    # can't change accessible_location_ids, and they will always be used to filter the export, but locations are
    # user configurable
    accessible_location_ids = ListProperty(StringProperty)
    locations = ListProperty(StringProperty)
    date_period = SchemaProperty(DatePeriod, default=None)
    users = ListProperty(StringProperty)
    reporting_groups = ListProperty(StringProperty)
    user_types = ListProperty(IntegerProperty)
    can_access_all_locations = BooleanProperty(default=True)

    def is_location_safe_for_user(self, request):
        """
        Return True if the couch_user of the given request has permission to export data with this filter.
        """
        if request.couch_user.has_permission(
                request.domain, 'access_all_locations'):
            return True
        elif self.can_access_all_locations:
            return False
        elif not self.accessible_location_ids:
            # if accessible_location_ids is empty, then in theory the user could
            # have access to all data if can_access_all_locations was ever set
            # to False. We need to prevent this from ever happening.
            return False
        else:  # It can be restricted by location
            users_accessible_locations = SQLLocation.active_objects.accessible_location_ids(
                request.domain, request.couch_user
            )
            return set(self.accessible_location_ids).issubset(users_accessible_locations)


class CaseExportInstanceFilters(ExportInstanceFilters):
    sharing_groups = ListProperty(StringProperty)
    show_all_data = BooleanProperty()
    show_project_data = BooleanProperty(default=True)
    show_deactivated_data = BooleanProperty()


class FormExportInstanceFilters(ExportInstanceFilters):
    user_types = ListProperty(IntegerProperty, default=[HQUserType.ACTIVE, HQUserType.DEACTIVATED])


class ExportInstance(BlobMixin, Document):
    """
    This is an instance of an export. It contains the tables to export and
    other presentation properties.
    """

    name = StringProperty()
    domain = StringProperty()
    tables = ListProperty(TableConfiguration)
    export_format = StringProperty(default='xlsx')
    app_id = StringProperty()

    # The id of the schema that was used to generate the instance.
    # Used for information and debugging purposes
    schema_id = StringProperty()

    # Whether to split multiselects into multiple columns
    split_multiselects = BooleanProperty(default=False)

    # Whether to automatically convert dates to excel dates
    transform_dates = BooleanProperty(default=True)

    # Whether to typeset the cells in Excel 2007+ exports
    format_data_in_excel = BooleanProperty(default=False)

    # Whether the export is de-identified
    is_deidentified = BooleanProperty(default=False)

    # Keep reference to old schema id if we have converted it from the legacy infrastructure
    legacy_saved_export_schema_id = StringProperty()

    is_odata_config = BooleanProperty(default=False)

    is_daily_saved_export = BooleanProperty(default=False)
    auto_rebuild_enabled = BooleanProperty(default=True)

    show_det_config_download = BooleanProperty(default=False)

    # daily saved export fields:
    last_updated = DateTimeProperty()
    last_accessed = DateTimeProperty()
    last_build_duration = IntegerProperty()

    description = StringProperty(default='')

    sharing = StringProperty(default=SharingOption.EDIT_AND_EXPORT, choices=SharingOption.CHOICES)
    owner_id = StringProperty(default=None)
    selected_geo_property = StringProperty(default='')

    _blobdb_type_code = CODES.data_export

    class Meta(object):
        app_label = 'export'

    @classmethod
    def wrap(cls, data):
        from corehq.apps.export.views.utils import clean_odata_columns
        export_instance = super(ExportInstance, cls).wrap(data)
        if export_instance.is_odata_config:
            clean_odata_columns(export_instance)
        return export_instance

    @property
    def is_safe(self):
        """For compatibility with old exports"""
        return self.is_deidentified

    @property
    def defaults(self):
        if self.type == FORM_EXPORT:
            return FormExportInstanceDefaults
        elif self.type == SMS_EXPORT:
            return SMSExportInstanceDefaults
        else:
            return CaseExportInstanceDefaults

    def get_filters(self):
        """
        Return a list of export.filters.ExportFilter objects
        """
        raise NotImplementedError

    @property
    @memoized
    def has_multimedia(self):
        for table in self.tables:
            for column in table.selected_columns:
                if isinstance(column, MultiMediaExportColumn):
                    return True
        return False

    @property
    def selected_tables(self):
        return [t for t in self.tables if t.selected]

    def get_table(self, path):
        for table in self.tables:
            if table.path == path:
                return table
        return None

    @classmethod
    def _new_from_schema(cls, schema, export_settings=None):
        raise NotImplementedError()

    @classmethod
    def generate_instance_from_schema(
        cls,
        schema,
        saved_export=None,
        auto_select=True,
        export_settings=None,
        load_deprecated=False
    ):
        """Given an ExportDataSchema, this will generate an ExportInstance"""
        if saved_export:
            instance = saved_export
        else:
            instance = cls._new_from_schema(schema, export_settings)

        instance.name = instance.name or instance.defaults.get_default_instance_name(schema)
        instance.app_id = schema.app_id
        instance.schema_id = schema._id

        group_schemas = schema.group_schemas
        if not group_schemas:
            return instance

        latest_app_ids_and_versions = get_latest_app_ids_and_versions(
            schema.domain,
            getattr(schema, 'app_id', None),
        )
        for group_schema in group_schemas:
            table = instance.get_table(group_schema.path) or TableConfiguration(
                path=group_schema.path,
                label=instance.defaults.get_default_table_name(group_schema.path),
                selected=instance.defaults.default_is_table_selected(group_schema.path),
            )
            table.is_deleted = is_occurrence_deleted(
                group_schema.last_occurrences,
                latest_app_ids_and_versions,
            ) and not group_schema.inferred

            prev_index = 0
            for item in group_schema.items:
                index, column = table.get_column(
                    item.path, item.doc_type, None
                )
                is_deprecated = False
                if schema.type == 'case' and item.label in get_deprecated_fields(schema.domain, schema.case_type):
                    is_deprecated = True
                    item.tag = 'deprecated'
                if not column:
                    if is_deprecated and not load_deprecated:
                        continue

                    column = ExportColumn.create_default_from_export_item(
                        table.path,
                        item,
                        latest_app_ids_and_versions,
                        auto_select,
                        is_deprecated
                    )
                    if prev_index:
                        # if it's a new column, insert it right after the previous column
                        index = prev_index + 1
                        table.columns.insert(index, column)
                    else:
                        table.columns.append(column)
                else:
                    if column.selected:
                        column.is_deprecated = is_deprecated
                    elif is_deprecated and not load_deprecated:
                        table.columns.remove(column)
                        continue

                # Ensure that the item is up to date
                column.item = item

                # Need to rebuild tags and other flags based on new build ids
                column.update_properties_from_app_ids_and_versions(latest_app_ids_and_versions)
                prev_index = index

            instance._insert_system_properties(instance.domain, schema.type, table)
            table.columns = cls._move_selected_columns_to_top(table.columns)

            if not instance.get_table(group_schema.path):
                instance.tables.append(table)

        return instance

    def can_edit(self, user):
        return self.owner_id is None or self.owner_id == user.get_id or (
            self.sharing == SharingOption.EDIT_AND_EXPORT
            and user.can_edit_shared_exports(self.domain)
        )

    @classmethod
    def _move_selected_columns_to_top(cls, columns):
        ordered_columns = []
        ordered_columns.extend([column for column in columns if column.selected])
        ordered_columns.extend([column for column in columns if not column.selected])
        return ordered_columns

    def _insert_system_properties(self, domain, export_type, table):
        from corehq.apps.export.system_properties import (
            BOTTOM_MAIN_CASE_TABLE_PROPERTIES,
            BOTTOM_MAIN_FORM_TABLE_PROPERTIES,
            CASE_HISTORY_PROPERTIES,
            PARENT_CASE_TABLE_PROPERTIES,
            ROW_NUMBER_COLUMN,
            SMS_TABLE_PROPERTIES,
            STOCK_COLUMN,
            TOP_MAIN_CASE_TABLE_PROPERTIES,
            TOP_MAIN_FORM_TABLE_PROPERTIES,
        )

        nested_repeat_count = len([node for node in table.path if node.is_repeat])
        column_initialization_data = {
            'repeat': nested_repeat_count,  # Used for determining the proper row column
            'domain': domain,  # Used for the StockExportColumn
        }
        if export_type == FORM_EXPORT:
            if table.path == MAIN_TABLE:
                self.__insert_system_properties(
                    table,
                    TOP_MAIN_FORM_TABLE_PROPERTIES,
                    **column_initialization_data
                )
                self.__insert_system_properties(
                    table,
                    BOTTOM_MAIN_FORM_TABLE_PROPERTIES,
                    top=False,
                    **column_initialization_data
                )
                self.__insert_case_name(table, top=False)
            else:
                self.__insert_system_properties(table, [ROW_NUMBER_COLUMN], **column_initialization_data)
        elif export_type == CASE_EXPORT:
            if table.path == MAIN_TABLE or ALL_CASE_TYPE_TABLE in table.path:
                if Domain.get_by_name(domain).commtrack_enabled:
                    top_properties = TOP_MAIN_CASE_TABLE_PROPERTIES + [STOCK_COLUMN]
                else:
                    top_properties = TOP_MAIN_CASE_TABLE_PROPERTIES
                self.__insert_system_properties(
                    table,
                    top_properties,
                    **column_initialization_data
                )
                self.__insert_system_properties(
                    table,
                    BOTTOM_MAIN_CASE_TABLE_PROPERTIES,
                    top=False,
                    **column_initialization_data
                )
            elif table.path == CASE_HISTORY_TABLE:
                self.__insert_system_properties(table, CASE_HISTORY_PROPERTIES, **column_initialization_data)
            elif table.path == PARENT_CASE_TABLE:
                self.__insert_system_properties(table, PARENT_CASE_TABLE_PROPERTIES,
                        **column_initialization_data)
        elif export_type == SMS_EXPORT:
            if table.path == MAIN_TABLE:
                self.__insert_system_properties(table, SMS_TABLE_PROPERTIES, **column_initialization_data)

    def __insert_system_properties(self, table, properties, top=True, **column_initialization_data):
        """
        Inserts system properties into the table configuration

        :param table: A TableConfiguration instance
        :param properties: A list of ExportColumn that represent system properties to be added to the table
        :param top: When True inserts the columns at the top, when false at the bottom
        :param column_initialization_data: Extra data to be passed to the column if needed on initialization
        """
        properties = list(map(copy, properties))
        if top:
            properties = reversed(properties)

        insert_fn = self._get_insert_fn(table, top)

        domain = column_initialization_data.get('domain')
        for static_column in properties:
            index, existing_column = table.get_column(
                static_column.item.path,
                static_column.item.doc_type,
                static_column.item.transform,
            )
            column = (existing_column or static_column)
            if isinstance(column, RowNumberColumn):
                column.update_nested_repeat_count(column_initialization_data.get('repeat'))
            elif isinstance(column, StockExportColumn):
                column.update_domain(domain)

            if not existing_column:
                if static_column.label in ['case_link', 'form_link'] and self.get_id:
                    static_column.selected = False
                insert_fn(static_column)

    @classmethod
    def __insert_case_name(cls, table, top=True):
        """
        Inserts a case_name column if necessary

        :param table: A TableConfiguration instance
        :param top: When True inserts the columns at the top, when false at the bottom
        """
        insert_fn = cls._get_insert_fn(table, top)

        def consider(column):
            return not isinstance(column, UserDefinedExportColumn)

        def is_case_name(column):
            return (
                column.item.path[-1].name == 'case_name'
                or (column.item.path[-1].name == '@case_id' and column.item.transform == CASE_NAME_TRANSFORM)
            )

        from corehq.apps.export.system_properties import get_case_name_column
        case_id_columns = {
            _path_nodes_to_string(column.item.path[:-1]): column
            for column in table.columns if consider(column) and column.item.path[-1].name == '@case_id'
        }
        case_name_columns = {
            _path_nodes_to_string(column.item.path[:-1]): column
            for column in table.columns if consider(column) and is_case_name(column)
        }
        for path, column in case_id_columns.items():
            if path not in case_name_columns:
                insert_fn(get_case_name_column(column.item))

    @staticmethod
    def _get_insert_fn(table, top):
        if top:
            return partial(table.columns.insert, 0)
        else:
            return table.columns.append

    @property
    def file_size(self):
        """
        Return the size of the pre-computed export.
        Only daily saved exports could have a pre-computed export.
        """
        try:
            return self.blobs[DAILY_SAVED_EXPORT_ATTACHMENT_NAME].content_length
        except KeyError:
            return 0

    @property
    def filename(self):
        return "%s.%s" % (self.name, Format.from_format(self.export_format).extension)

    def has_file(self):
        """
        Return True if there is a pre-computed export saved for this instance.
        Only daily saved exports could have a pre-computed export.
        """
        return DAILY_SAVED_EXPORT_ATTACHMENT_NAME in self.blobs

    def set_payload(self, payload):
        """
        Set the pre-computed export for this instance.
        Only daily saved exports could have a pre-computed export.
        """
        self.put_attachment(payload, DAILY_SAVED_EXPORT_ATTACHMENT_NAME)

    def get_payload(self, stream=False):
        """
        Get the pre-computed export for this instance.
        Only daily saved exports could have a pre-computed export.
        """
        return self.fetch_attachment(DAILY_SAVED_EXPORT_ATTACHMENT_NAME, stream=stream)

    def copy_export(self):
        export_json = self.to_json()
        del export_json['_id']
        del export_json['external_blobs']
        export_json['name'] = '{} - Copy'.format(self.name)
        new_export = self.__class__.wrap(export_json)
        return new_export

    def error_messages(self):
        error_messages = []
        if self.export_format == 'xls':
            for table in self.tables:
                if len(table.selected_columns) > 255:
                    error_messages.append(_(
                        "XLS format does not support more than 255 columns. "
                        "Please select a different file type"
                    ))
                    break

        return error_messages


class CaseExportInstance(ExportInstance):
    case_type = StringProperty()
    type = CASE_EXPORT

    # static filters to limit the data in this export
    # filters are only used in daily saved and HTML (dashboard feed) exports
    filters = SchemaProperty(CaseExportInstanceFilters)

    @classmethod
    def wrap(cls, data):
        export_instance = super(CaseExportInstance, cls).wrap(data)
        if export_instance.is_odata_config:
            for table in export_instance.tables:
                for column in table.columns:
                    if not column.item.transform and [path_node.name for path_node in column.item.path] == ['_id']:
                        column.label = 'caseid'
                        column.selected = True
        return export_instance

    @property
    def identifier(self):
        return self.case_type

    @classmethod
    def _new_from_schema(cls, schema, export_settings=None):
        if export_settings is not None:
            return cls(
                domain=schema.domain,
                case_type=schema.case_type,
                export_format=export_settings.cases_filetype,
                transform_dates=export_settings.cases_auto_convert,
            )
        else:
            return cls(
                domain=schema.domain,
                case_type=schema.case_type,
            )

    def get_filters(self):
        if self.filters:
            from corehq.apps.export.forms import CaseExportFilterBuilder
            filter_builder = CaseExportFilterBuilder(
                Domain.get_by_name(self.domain), get_timezone_for_domain(self.domain)
            )
            return filter_builder.get_filters(
                self.filters.can_access_all_locations,
                self.filters.accessible_location_ids,
                self.filters.show_all_data,
                self.filters.show_project_data,
                self.filters.show_deactivated_data,
                self.filters.user_types,
                self.filters.date_period,
                self.filters.sharing_groups + self.filters.reporting_groups,
                self.filters.locations,
                self.filters.users,
            )
        return []

    @property
    def has_case_history_table(self):
        case_history_table = [table for table in self.tables if table.label == 'Case History']
        return any(
            column.selected
            for table in case_history_table
            for column in table.columns
        )

    def get_query(self, include_filters=True):
        # Add all case types if doing a bulk export
        # These case types will be the first element in the table path
        case_types = self.case_type
        if case_types == ALL_CASE_TYPE_EXPORT:
            case_types = []
            for table in self.selected_tables:
                path_names = [path.name for path in table.path if path.name != ALL_CASE_TYPE_EXPORT]
                case_types += path_names

        query = get_case_export_base_query(self.domain, case_types)
        if include_filters:
            for filter in self.get_filters():
                query = query.filter(filter.to_es_filter())

        return query

    def get_rows(self):
        return self.get_query().values()

    def get_count(self):
        return self.get_query().count()


class FormExportInstance(ExportInstance):
    xmlns = StringProperty()
    type = FORM_EXPORT

    # Whether to include duplicates and other error'd forms in export
    include_errors = BooleanProperty(default=False)

    # static filters to limit the data in this export
    # filters are only used in daily saved and HTML (dashboard feed) exports
    filters = SchemaProperty(FormExportInstanceFilters)

    @classmethod
    def wrap(cls, data):
        export_instance = super(FormExportInstance, cls).wrap(data)
        if export_instance.is_odata_config:
            for table in export_instance.tables:
                for column in table.columns:
                    if not column.item.transform and (
                        [path_node.name for path_node in column.item.path] == ['form', 'meta', 'instanceID']
                    ):
                        column.label = 'formid'
                        column.selected = True
        return export_instance

    @property
    def identifier(self):
        return self.xmlns

    @property
    def formname(self):
        return xmlns_to_name(self.domain, self.xmlns, self.app_id)

    @classmethod
    def _new_from_schema(cls, schema, export_settings=None):
        if export_settings is not None:
            return cls(
                domain=schema.domain,
                xmlns=schema.xmlns,
                app_id=schema.app_id,
                export_format=export_settings.forms_filetype,
                transform_dates=export_settings.forms_auto_convert,
                format_data_in_excel=export_settings.forms_auto_format_cells,
                split_multiselects=export_settings.forms_expand_checkbox,
            )
        else:
            return cls(
                domain=schema.domain,
                xmlns=schema.xmlns,
                app_id=schema.app_id,
            )

    def get_filters(self):
        if self.filters:
            from corehq.apps.export.forms import FormExportFilterBuilder
            filter_builder = FormExportFilterBuilder(
                Domain.get_by_name(self.domain), get_timezone_for_domain(self.domain)
            )
            return filter_builder.get_filters(
                self.filters.can_access_all_locations,
                self.filters.accessible_location_ids,
                self.filters.reporting_groups,
                self.filters.user_types,
                self.filters.users,
                self.filters.locations,
                self.filters.date_period,
            )
        return []

    def get_query(self, include_filters=True):
        query = get_form_export_base_query(self.domain, self.app_id, self.xmlns, self.include_errors)
        if include_filters:
            for filter in self.get_filters():
                query = query.filter(filter.to_es_filter())

        return query

    def get_rows(self):
        return self.get_query().values()

    def get_count(self):
        return self.get_query().count()


class SMSExportInstance(ExportInstance):
    type = SMS_EXPORT
    identifier = None
    name = "Messages"

    @classmethod
    def _new_from_schema(cls, schema, export_settings=None):
        main_table = TableConfiguration(
            label='Messages',
            path=MAIN_TABLE,
            selected=True,
            columns=[],
        )
        if schema.include_metadata:
            main_table.columns.append(ExportColumn(
                label="Message Log ID",
                item=ExportItem(
                    path=[PathNode(name='_id')]
                ),
                selected=True,
            ))

        instance = cls(domain=schema.domain, tables=[main_table])
        instance._insert_system_properties(instance.domain, schema.type, instance.tables[0])
        return instance

    def get_query(self, include_filters=True):
        query = get_sms_export_base_query(self.domain)
        if include_filters:
            for filter in self.get_filters():
                query = query.filter(filter.to_es_filter())

        return query


class DataSourceExportInstance(ExportInstance):
    type = 'datasource'
    data_source_id = StringProperty()


class ExportInstanceDefaults(object):
    """
    This class is responsible for generating defaults for various aspects of the export instance
    """
    @staticmethod
    def get_default_instance_name(schema):
        raise NotImplementedError()

    @staticmethod
    def get_default_table_name(table_path):
        raise NotImplementedError()

    @staticmethod
    def default_is_table_selected(path):
        """
        Based on the path, determines whether the table should be selected by default
        """
        return path == MAIN_TABLE or ALL_CASE_TYPE_TABLE in path


class FormExportInstanceDefaults(ExportInstanceDefaults):

    @staticmethod
    def get_default_instance_name(schema):
        return _('{name} (created {date})').format(
            name=xmlns_to_name(schema.domain, schema.xmlns, schema.app_id, separator=" - "),
            date=datetime.now().strftime('%Y-%m-%d')
        )

    @staticmethod
    def get_default_table_name(table_path):
        if table_path == MAIN_TABLE:
            return _('Forms')
        else:
            if not len(table_path):
                return _('Repeat')

            default_table_name = table_path[-1].name
            # We are probably exporting a model iteration question
            if default_table_name == 'item' and len(table_path) > 1:
                default_table_name = '{}.{}'.format(table_path[-2].name, default_table_name)
            return _('Repeat: {}').format(default_table_name)


class CaseExportInstanceDefaults(ExportInstanceDefaults):

    @staticmethod
    def get_default_table_name(table_path):
        if table_path == MAIN_TABLE:
            return _('Cases')
        elif table_path == CASE_HISTORY_TABLE:
            return _('Case History')
        elif table_path == PARENT_CASE_TABLE:
            return _('Parent Cases')
        elif ALL_CASE_TYPE_TABLE in table_path:
            return _(table_path[0].name)
        else:
            return _('Unknown')

    @staticmethod
    def get_default_instance_name(schema):
        return _('{name} (created {date})').format(
            name=schema.case_type,
            date=datetime.now().strftime('%Y-%m-%d')
        )


class SMSExportInstanceDefaults(ExportInstanceDefaults):
    @staticmethod
    def get_default_table_name(table_path):
        if table_path == MAIN_TABLE:
            return _('Messages')
        else:
            return _('Unknown')

    @staticmethod
    def get_default_instance_name(schema):
        return _('Messages (created {date})').format(date=datetime.now().strftime('%Y-%m-%d'))


class ExportRow(object):

    def __init__(self, data, hyperlink_column_indices=(),
                 skip_excel_formatting=()):
        self.data = data
        self.hyperlink_column_indices = hyperlink_column_indices
        self.skip_excel_formatting = skip_excel_formatting


class ScalarItem(ExportItem):
    """
    A text, numeric, date, etc. question or case property
    """


class LabelItem(ExportItem):
    """
    An item that refers to a label question
    """


class CaseIndexItem(ExportItem):
    """
    An item that refers to a case index.

    See CaseIndexExportColumn
    """

    @property
    def case_type(self):
        return self.path[1].name


class GeopointItem(ExportItem):
    """
    A GPS coordinate question.

    See SplitGPSExportColumn
    """


class MultiMediaItem(ExportItem):
    """
    An item that references multimedia.

    See MultiMediaExportColumn
    """


class StockItem(ExportItem):
    """
    An item that references a stock question (balance, transfer, dispense, receive)

    See StockFormExportColumn
    """

    @classmethod
    def create_from_question(cls, question, path, app_id, app_version, repeats):
        """
        Overrides ExportItem's create_from_question, by allowing an explicit path
        that may not match the question's value key
        """
        return cls(
            path=_question_path_to_path_nodes(path, repeats),
            label=question['label'],
            last_occurrences={app_id: app_version},
        )


class Option(DocumentSchema):
    """
    This object represents a multiple choice question option.

    last_occurrences is a dictionary of app_ids mapped to the last version that the options was present.
    """
    last_occurrences = DictProperty()
    value = StringProperty()


class MultipleChoiceItem(ExportItem):
    """
    A multiple choice question or case property
    Choices is the union of choices for the question in each of the builds with
    this question.

    See SplitExportColumn
    """
    options = SchemaListProperty(Option)

    @classmethod
    def create_from_question(cls, question, app_id, app_version, repeats):
        item = super(MultipleChoiceItem, cls).create_from_question(question, app_id, app_version, repeats)

        for option in question['options']:
            item.options.append(Option(
                last_occurrences={app_id: app_version},
                value=option['value']
            ))
        return item

    @classmethod
    def merge(cls, one, two):
        item = super(MultipleChoiceItem, cls).merge(one, two)
        options = _merge_lists(one.options, two.options,
            keyfn=lambda i: i.value,
            resolvefn=lambda option1, option2:
                Option(
                    value=option1.value,
                    last_occurrences=_merge_dicts(option1.last_occurrences, option2.last_occurrences)
                ),
        )

        item.options = options
        return item


class ExportGroupSchema(DocumentSchema, ReadablePathMixin):
    """
    An object representing the `ExportItem`s that would appear in a single export table, such as all the
    questions in a particular repeat group, or all the questions not in any repeat group.
    """
    path = SchemaListProperty(PathNode)
    items = SchemaListProperty(ExportItem)
    last_occurrences = DictProperty()

    # True if this item was inferred from different actions in HQ (i.e. case upload)
    # False if the item was found in the application structure
    inferred = BooleanProperty(default=False)


class InferredExportGroupSchema(ExportGroupSchema):
    """
    Same as an ExportGroupSchema with a few utility methods
    """

    def put_item(self, path, inferred_from=None, item_cls=ScalarItem):
        assert self.path == path[:len(self.path)], "ExportItem's path doesn't start with the table"
        item = self.get_item(path)

        if item:
            item.inferred_from.add(inferred_from or UNKNOWN_INFERRED_FROM)
            return item

        item = item_cls(
            path=path,
            label='.'.join([node.name for node in path]),
            inferred=True,
            inferred_from=set([inferred_from or UNKNOWN_INFERRED_FROM])
        )
        self.items.append(item)
        return item

    def get_item(self, path):
        for item in self.items:
            if item.path == path and isinstance(item, ExportItem):
                return item
        return None


class InferredSchema(Document):
    """
    An inferred schema is information we know about the application that is not
    in the application itself. For example, inferred schemas can keep track of
    case properties that were uploaded during a case import. This way we have a
    record of these properties even though they were not in the application
    structure.
    """
    domain = StringProperty(required=True)
    created_on = DateTimeProperty(default=datetime.utcnow)
    group_schemas = SchemaListProperty(InferredExportGroupSchema)
    version = IntegerProperty(default=1)

    # This normally contains a mapping of app_id to the version number. For
    # inferred schemas this'll always be an empty dictionary since it is
    # inferred. It is needed because when schemas are merged, it's expected
    # that all schema duck types have this property.
    last_app_versions = DictProperty()

    class Meta(object):
        app_label = 'export'

    def put_group_schema(self, path):
        group_schema = self.get_group_schema(path)

        if group_schema:
            return group_schema

        group_schema = InferredExportGroupSchema(
            path=path,
            items=[],
            inferred=True,
        )
        self.group_schemas.append(group_schema)
        return group_schema

    def get_group_schema(self, path):
        for group_schema in self.group_schemas:
            if group_schema.path == path:
                return group_schema
        return None

    @property
    def identifier(self):
        raise NotImplementedError()


class CaseInferredSchema(InferredSchema):
    case_type = StringProperty(required=True)

    @property
    def identifier(self):
        return self.case_type


class FormInferredSchema(InferredSchema):
    """This was used during the migratoin from the old models to capture
    export items that could not be found in the current apps.

    See https://github.com/dimagi/commcare-hq/blob/34a9459462271cf2dcd7562b36cc86e300d343b8/corehq/apps/export/utils.py#L246-L265  # noqa: E501
    """
    xmlns = StringProperty(required=True)
    app_id = StringProperty()

    @property
    def identifier(self):
        return self.xmlns


class ExportDataSchema(Document):
    """
    An object representing the things that can be exported for a particular
    form xmlns or case type. It contains a list of ExportGroupSchema.
    """
    domain = StringProperty(required=True)
    created_on = DateTimeProperty(default=datetime.utcnow)
    group_schemas = SchemaListProperty(ExportGroupSchema)
    app_id = StringProperty()
    version = IntegerProperty(default=1)

    # A map of app_id to app_version. Represents the last time it saw an app and at what version
    last_app_versions = DictProperty()

    class Meta(object):
        app_label = 'export'

    def get_number_of_apps_to_process(self):
        app_ids_for_domain = self._get_current_app_ids_for_domain(self.domain, self.app_id)
        return len(self._get_app_build_ids_to_process(
            self.domain,
            app_ids_for_domain,
            self.last_app_versions,
        ))

    @classmethod
    def generate_empty_schema(cls, domain, identifier):
        """
        Builds a schema, without processing any Application builds.
        This is primarily used for bulk case exports, as the processing of Application
        builds will happen later in an async task when saving the export instance.
        """
        current_schema = cls()

        current_schema.domain = domain
        current_schema.app_id = None
        current_schema.version = cls.schema_version()
        current_schema._set_identifier(identifier)

        current_schema = cls._save_export_schema(
            current_schema,
            original_id=None,
            original_rev=None
        )
        return current_schema

    @classmethod
    def generate_schema(
        cls,
        domain,
        app_id,
        identifier,
        force_rebuild=False,
        only_process_current_builds=False,
        only_use_data_dictionary=False,
        task=None,
    ):
        """
        Builds a schema from Application builds for a given identifier

        :param domain: The domain that the export belongs to
        :param app_id: The app_id that the export belongs to or None if
            the export is not associated with an app.
        :param identifier: The unique identifier of the schema being
            exported: case_type for Case Exports and xmlns for Form
            Exports
        :param only_process_current_builds: Only process the current
            apps, not any builds. This means that deleted items may not
            be present in the schema since past builds have not been
            processed.
        :param only_use_data_dictionary: Only use Data dictionary to
            update the current schema
        :param task: A celery task to update the progress of the build
        :returns: Returns a ExportDataSchema instance
        """

        original_id, original_rev = None, None
        current_schema = cls.get_latest_export_schema(domain, app_id, identifier)
        if (current_schema
                and not force_rebuild
                and current_schema.version == cls.schema_version()):
            original_id, original_rev = current_schema._id, current_schema._rev
        else:
            current_schema = cls()

        if only_use_data_dictionary:
            current_schema = cls._update_schema_from_data_dictionary(
                domain, current_schema, identifier, task)
        else:
            app_ids_for_domain = cls._get_current_app_ids_for_domain(domain, app_id)
            app_build_ids = []
            if not only_process_current_builds:
                app_build_ids = cls._get_app_build_ids_to_process(
                    domain,
                    app_ids_for_domain,
                    current_schema.last_app_versions,
                )
            app_build_ids.extend(app_ids_for_domain)
            current_schema = cls._process_apps_for_export(domain, current_schema, identifier, app_build_ids, task)

        inferred_schema = cls._get_inferred_schema(domain, app_id, identifier)
        if inferred_schema:
            current_schema = cls._merge_schemas(current_schema, inferred_schema)

        try:
            current_schema = cls._reorder_schema_from_app(current_schema, app_id, identifier)
        except Exception as e:
            logging.exception('Failed to process app during reorder {}. {}'.format(app_id, e))

        current_schema.domain = domain
        current_schema.app_id = app_id
        current_schema.version = cls.schema_version()
        current_schema._set_identifier(identifier)

        current_schema = cls._save_export_schema(
            current_schema,
            original_id,
            original_rev
        )
        return current_schema

    @classmethod
    def _update_schema_from_data_dictionary(cls, domain, current_schema, case_type, task):
        data_dict_props_by_case_type = get_data_dict_props_by_case_type(domain)

        if case_type not in data_dict_props_by_case_type:
            raise Exception("Case type not found in data dictionary")

        case_property_mapping = {
            case_type: data_dict_props_by_case_type[case_type]
        }

        case_schema = cls._generate_schema_from_case_property_mapping(case_property_mapping)
        current_schema = cls._merge_schemas(current_schema, case_schema)

        set_task_progress(task, current=1, total=1, src='ExportDataSchema._generate_schema_from_data_dictionary')
        return current_schema

    @classmethod
    def _reorder_schema_from_app(cls, current_schema, app_id, identifier):
        try:
            app = get_app(current_schema.domain, app_id)
        except Http404:
            return current_schema

        if isinstance(app, RemoteApp):
            return current_schema

        ordered_schema = cls._process_app_build(
            cls(),
            app,
            identifier,
        )
        return cls._reorder_schema_from_schema(current_schema, ordered_schema)

    @classmethod
    def _reorder_schema_from_schema(cls, current_schema, ordered_schema):
        # First create a dictionary that maps item path to order number
        # {
        #   (PathNode(), PathNode()): 0
        #   (PathNode(), PathNode()): 1
        #   ...
        # }

        orders = {}
        for group_schema in ordered_schema.group_schemas:
            for idx, item in enumerate(group_schema.items):
                orders[item] = idx

        # Next iterate through current schema and order the ones that have an order
        # and put the rest at the bottom. The ones not ordered are deleted items
        for group_schema in current_schema.group_schemas:
            ordered_items = [None] * len(group_schema.items)
            unordered_items = []
            for idx, item in enumerate(group_schema.items):
                if item in orders:
                    ordered_items[orders[item]] = item
                else:
                    unordered_items.append(item)
            group_schema.items = [_f for _f in ordered_items if _f] + unordered_items
        return current_schema

    @classmethod
    def _merge_schemas(cls, *schemas):
        """Merges two ExportDataSchemas together

        :param schema1: The first ExportDataSchema
        :param schema2: The second ExportDataSchema
        :returns: The merged ExportDataSchema
        """

        schema = cls()

        def resolvefn(group_schema1, group_schema2):

            def keyfn(export_item):
                return export_item

            group_schema1.last_occurrences = _merge_dicts(
                group_schema1.last_occurrences,
                group_schema2.last_occurrences
            )
            group_schema1.inferred = group_schema1.inferred or group_schema2.inferred
            items = _merge_lists(
                group_schema1.items,
                group_schema2.items,
                keyfn=keyfn,
                resolvefn=lambda item1, item2: item1.__class__.merge(item1, item2),
            )
            group_schema1.items = items
            return group_schema1

        previous_group_schemas = schemas[0].group_schemas
        last_app_versions = schemas[0].last_app_versions
        for current_schema in schemas[1:]:
            group_schemas = _merge_lists(
                previous_group_schemas,
                current_schema.group_schemas,
                keyfn=lambda group_schema: _path_nodes_to_string(group_schema.path),
                resolvefn=resolvefn,
            )
            previous_group_schemas = group_schemas
            last_app_versions = _merge_dicts(
                last_app_versions,
                current_schema.last_app_versions
            )

        schema.group_schemas = group_schemas
        schema.last_app_versions = last_app_versions

        return schema

    def record_update(self, app_id, app_version):
        self.last_app_versions[app_id] = max(
            self.last_app_versions.get(app_id, 0),
            app_version or 0,
        )

    @staticmethod
    def _save_export_schema(current_schema, original_id, original_rev):
        """
        Given a schema object, this function saves the object and ensures that the
        ID remains the same as the previous save if there existed a previous version.
        """
        if original_id and original_rev:
            current_schema._id = original_id
            current_schema._rev = original_rev

        try:
            current_schema.save()
        except ResourceConflict:
            # It's possible that another process updated the schema before we
            # got to it. If so, we want to overwrite those changes because we
            # have the most recently built schema.
            current_schema._rev = ExportDataSchema.get_db().get_rev(current_schema._id)
            current_schema.save()

        return current_schema

    @classmethod
    def _process_apps_for_export(cls, domain, schema, identifier, app_build_ids, task):
        apps_processed = 0
        for app_doc in iter_docs(Application.get_db(), app_build_ids, chunksize=10):
            doc_type = app_doc.get('doc_type', '')
            if doc_type not in ('Application', 'LinkedApplication', 'Application-Deleted'):
                continue
            if (not app_doc.get('has_submissions', False)
                    and app_doc.get('copy_of')):
                continue

            try:
                app = Application.wrap(app_doc)
            except BadValueError as err:
                logging.exception(
                    f"Bad definition for Application {app_doc['_id']}",
                    exc_info=err,
                )
                continue

            try:
                schema = cls._process_app_build(
                    schema,
                    app,
                    identifier,
                )
            except Exception as e:
                logging.exception('Failed to process app {}. {}'.format(app._id, e))
                continue

            if app.copy_of:
                schema.record_update(app.copy_of, app.version)

            apps_processed += 1
            set_task_progress(task, apps_processed, len(app_build_ids))

        return schema


class FormExportDataSchema(ExportDataSchema):

    xmlns = StringProperty(required=True)
    datatype_mapping = defaultdict(lambda: ScalarItem, {
        'MSelect': MultipleChoiceItem,
        'Geopoint': GeopointItem,
        'Image': MultiMediaItem,
        'Audio': MultiMediaItem,
        'Video': MultiMediaItem,
        'Trigger': LabelItem,
    })

    @property
    def type(self):
        return FORM_EXPORT

    @classmethod
    def schema_version(cls):
        return FORM_DATA_SCHEMA_VERSION

    @classmethod
    def _get_inferred_schema(cls, domain, app_id, xmlns):
        return get_form_inferred_schema(domain, app_id, xmlns)

    def _set_identifier(self, form_xmlns):
        self.xmlns = form_xmlns

    @classmethod
    def _get_current_app_ids_for_domain(cls, domain, app_id):
        """Get all app IDs of 'current' apps that should be included in this schema"""
        if not app_id:
            return []
        return [app_id]

    @staticmethod
    def _get_app_build_ids_to_process(domain, app_ids, last_app_versions):
        """Get all built apps that should be included in this schema"""
        app_id = app_ids[0] if app_ids else None
        return get_built_app_ids_with_submissions_for_app_id(
            domain,
            app_id,
            last_app_versions.get(app_id)
        )

    @staticmethod
    def get_latest_export_schema(domain, app_id, form_xmlns):
        return get_latest_form_export_schema(domain, app_id, form_xmlns)

    @classmethod
    def _process_app_build(cls, current_schema, app, form_xmlns):
        forms = app.get_forms_by_xmlns(form_xmlns, log_missing=False)
        if not forms:
            return current_schema

        xform = forms[0].wrapped_xform()  # This will be the same for any form in the list
        xform_schema = cls._generate_schema_from_xform(
            xform,
            app.langs,
            app.origin_id,  # If it's not a copy, must be current
            app.version,
        )

        schemas = [current_schema, xform_schema]
        repeats = cls._get_repeat_paths(xform, app.langs)
        schemas.extend(cls._add_export_items_for_cases(xform_schema.group_schemas[0], forms, repeats))

        return cls._merge_schemas(*schemas)

    @classmethod
    def _add_export_items_for_cases(cls, root_group_schema, forms, repeats):
        """Updates the root_group_schema in place and also returns a new schema for subcases
        in repeats (if any).

        :param root_group_schema:
        :param forms: List of forms. Assume all have the same XMLNS
        :param repeats: List of repeat paths in the form.
        :return: FormDataExportSchema containing one group schema for each
        """
        assert root_group_schema.path == []

        case_updates = OrderedSet()
        for form in forms:
            for update in form.get_case_updates_for_case_type(form.get_module().case_type):
                case_updates.add(update)

        for form in forms:
            if not form.uses_cases:
                continue

            if form.form_type == 'module_form':
                case_properties = {}
                actions = form.active_actions()
                if 'open_case' in actions:
                    action = actions['open_case']
                    if 'external_id' in action and action.external_id:
                        case_properties['external_id'] = action.external_id
                if 'update_case' in actions:
                    case_properties.update(actions['update_case'].update)

                cls._add_export_items_for_case(
                    root_group_schema, '/data', case_properties,
                    'case', repeats=[], create='open_case' in actions, close='close_case' in actions
                )

                if 'usercase_update' in actions and actions['usercase_update'].update:
                    cls._add_export_items_for_case(
                        root_group_schema, '/data/commcare_usercase', actions['usercase_update'].update,
                        'case', repeats=[], create='open_case' in actions, close='close_case' in actions
                    )
            else:
                all_actions = [form.actions]
                if hasattr(form, 'extra_actions'):
                    # shadow forms can have extra actions
                    all_actions.append(form.extra_actions)
                for actions in all_actions:
                    for action in actions.load_update_cases:
                        cls._add_export_items_for_case(
                            root_group_schema, '/data/{}'.format(action.form_element_name),
                            action.case_properties, action.case_tag, repeats=[],
                            create=False, close=action.close_condition.is_active()
                        )

                    for action in actions.open_cases:
                        if not action.is_subcase:
                            cls._add_export_items_for_case(
                                root_group_schema, '/data/{}'.format(action.form_element_name),
                                action.case_properties, action.case_tag, repeats=[],
                                create=True, close=action.close_condition.is_active()
                            )

        subcase_schema = cls()
        for form in forms:
            if isinstance(form.actions, AdvancedFormActions):
                actions = list(form.actions.get_open_subcase_actions())
            else:
                actions = list(form.actions.get_subcases())

            repeat_context_count = form.actions.count_subcases_per_repeat_context()

            for subcase_action in actions:
                if subcase_action.repeat_context:
                    root_path = subcase_action.repeat_context
                    if repeat_context_count[subcase_action.repeat_context] > 1:
                        root_path = '{}/{}'.format(root_path, subcase_action.form_element_name)

                    group_schema = ExportGroupSchema(
                        path=_question_path_to_path_nodes(root_path, repeats),
                        last_occurrences=root_group_schema.last_occurrences,
                    )
                    subcase_schema.group_schemas.append(group_schema)
                    cls._add_export_items_from_subcase_action(group_schema, root_path, subcase_action, repeats)
                else:
                    root_path = "/data/{}".format(subcase_action.form_element_name)  # always nest in root
                    cls._add_export_items_from_subcase_action(root_group_schema, root_path, subcase_action, [])

        return [subcase_schema] if subcase_schema.group_schemas else []

    @classmethod
    def _add_export_items_from_subcase_action(cls, group_schema, root_path, subcase_action, repeats):
        label_prefix = subcase_action.form_element_name
        index_relationships = []
        if isinstance(subcase_action, OpenSubCaseAction) and subcase_action.relationship:
            index_relationships = [CaseIndex(
                reference_id=DEFAULT_CASE_INDEX_IDENTIFIERS[subcase_action.relationship],
                relationship=subcase_action.relationship,
            )]
        elif hasattr(subcase_action, 'case_indices'):
            index_relationships = subcase_action.case_indices

        cls._add_export_items_for_case(
            group_schema, root_path, subcase_action.case_properties,
            label_prefix, repeats, case_indices=index_relationships
        )

    @classmethod
    def _add_export_items_for_case(cls, group_schema, root_path, case_properties, label_prefix,
                                   repeats, case_indices=None, create=True, close=False):
        def _add_to_group_schema(path, label, transform=None, datatype=None):
            group_schema.items.append(ExportItem(
                path=_question_path_to_path_nodes(path, repeats),
                label='{}.{}'.format(label_prefix, label),
                last_occurrences=group_schema.last_occurrences,
                tag=PROPERTY_TAG_CASE,
                transform=transform,
                datatype=datatype
            ))

        # Add case attributes
        for case_attribute, datatype in CASE_ATTRIBUTES.items():
            path = '{}/case/{}'.format(root_path, case_attribute)
            _add_to_group_schema(path, case_attribute, datatype=datatype)

        # Add case updates
        for case_property, case_path in case_properties.items():
            path_suffix = case_property
            path = '{}/case/update/{}'.format(root_path, path_suffix)
            _add_to_group_schema(path, 'update.{}'.format(case_property))

        # Add case create properties
        if create:
            for case_create_element in CASE_CREATE_ELEMENTS:
                path = '{}/case/create/{}'.format(root_path, case_create_element)
                _add_to_group_schema(path, 'create.{}'.format(case_create_element), datatype='string')

        if close:
            path = '{}/case/close'.format(root_path)
            _add_to_group_schema(path, 'close', transform=CASE_CLOSE_TO_BOOLEAN)

        # Add case index information
        if case_indices:
            for index in case_indices:
                props = ('#text', '@case_type',)
                if index.relationship != 'child':
                    props = props + ('@relationship',)
                for prop in props:
                    identifier = index.reference_id or 'parent'
                    path = '{}/case/index/{}/{}'.format(root_path, identifier, prop)
                    _add_to_group_schema(path, 'index.{}'.format(prop))

    @staticmethod
    def _get_repeat_paths(xform, langs):
        return [
            question['value']
            for question in xform.get_questions(langs, include_groups=True) if question['tag'] == 'repeat'
        ]

    @classmethod
    def _generate_schema_from_xform(cls, xform, langs, app_id, app_version):
        questions = xform.get_questions(langs, include_triggers=True)
        repeats = cls._get_repeat_paths(xform, langs)
        schema = cls()

        def question_keyfn(q):
            return q['repeat']

        question_groups = [
            (None, [q for q in questions if question_keyfn(q) is None])
        ] + [
            (x, list(y)) for x, y in groupby(
                sorted(
                    (q for q in questions if question_keyfn(q) is not None),
                    key=question_keyfn,
                ),
                question_keyfn
            )
        ]

        if None not in [x[0] for x in question_groups]:
            # If there aren't any questions in the main table, a group for
            # it anyways.
            question_groups = [(None, [])] + question_groups

        for group_path, group_questions in question_groups:
            # If group_path is None, that means the questions are part of the form and not a repeat group
            # inside of the form
            group_schema = ExportGroupSchema(
                path=_question_path_to_path_nodes(group_path, repeats),
                last_occurrences={app_id: app_version},
            )
            for question in group_questions:
                # Create ExportItem based on the question type
                if 'stock_type_attributes' in question:
                    items = cls._get_stock_items_from_question(
                        question,
                        app_id,
                        app_version,
                        repeats,
                    )
                    group_schema.items.extend(items)
                else:
                    item = cls.datatype_mapping[question['type']].create_from_question(
                        question,
                        app_id,
                        app_version,
                        repeats,
                    )
                    if question['value'].endswith('case/close'):
                        # for save to case
                        item.transform = CASE_CLOSE_TO_BOOLEAN
                    group_schema.items.append(item)

            schema.group_schemas.append(group_schema)

        return schema

    @staticmethod
    def _get_stock_items_from_question(question, app_id, app_version, repeats):
        """
        Creates a list of items from a stock type question
        """
        items = []

        # Strips the last value in the path
        # E.G. /data/balance/entry --> /data/balance
        parent_path = question['value'][:question['value'].rfind('/')]
        question_id = question['stock_type_attributes']['type']

        parent_path_and_question_id = '{}:{}'.format(parent_path, question_id)

        for attribute in question['stock_type_attributes']:
            items.append(StockItem.create_from_question(
                question,
                '{}/@{}'.format(parent_path_and_question_id, attribute),
                app_id,
                app_version,
                repeats,
            ))

        for attribute in question['stock_entry_attributes']:
            items.append(StockItem.create_from_question(
                question,
                '{}/{}/@{}'.format(parent_path_and_question_id, 'entry', attribute),
                app_id,
                app_version,
                repeats,
            ))

        return items

    @classmethod
    def _process_apps_for_export(cls, domain, schema, identifier, app_build_ids, task):
        return super(FormExportDataSchema, cls)._process_apps_for_export(
            domain,
            schema,
            identifier,
            app_build_ids,
            task
        )


class CaseExportDataSchema(ExportDataSchema):

    case_type = StringProperty(required=True)

    @property
    def type(self):
        return CASE_EXPORT

    def _set_identifier(self, case_type):
        self.case_type = case_type

    @classmethod
    def schema_version(cls):
        return CASE_DATA_SCHEMA_VERSION

    @classmethod
    def _get_inferred_schema(cls, domain, app_id, case_type):
        return get_case_inferred_schema(domain, case_type)

    @classmethod
    def _get_current_app_ids_for_domain(cls, domain, app_id):
        return get_app_ids_in_domain(domain)

    @staticmethod
    def _get_app_build_ids_to_process(domain, app_ids, last_app_versions):
        return get_built_app_ids_with_submissions_for_app_ids_and_versions(
            domain,
            app_ids,
            last_app_versions
        )

    @staticmethod
    def get_latest_export_schema(domain, app_id, case_type):
        return get_latest_case_export_schema(domain, case_type)

    @classmethod
    def _process_app_build(cls, current_schema, app, case_type):
        builder = ParentCasePropertyBuilder(
            app.domain,
            [app],
            include_parent_properties=False
        )
        case_property_mapping = builder.get_case_property_map([case_type])

        parent_types = builder.get_case_relationships_for_case_type(case_type)
        case_schemas = []
        case_schemas.append(cls._generate_schema_from_case_property_mapping(
            case_property_mapping,
            parent_types,
            app.origin_id,  # If not copy, must be current app
            app.version,
        ))
        if any([relationship_tuple[1] in ['parent', 'host'] for relationship_tuple in parent_types]):
            case_schemas.append(cls._generate_schema_for_parent_case(
                app.origin_id,
                app.version,
            ))

        case_schemas.append(cls._generate_schema_for_case_history(
            case_property_mapping,
            app.origin_id,
            app.version,
        ))
        case_schemas.append(current_schema)

        return cls._merge_schemas(*case_schemas)

    @classmethod
    def _generate_schema_from_case_property_mapping(cls, case_property_mapping,
                                                    parent_types=None, app_id=None, app_version=None):
        """
        Generates the schema for the main Case tab on the export page
        Includes system export properties for the case as well as properties for exporting parent case IDs
        if applicable.
        """
        assert len(list(case_property_mapping)) == 1
        schema = cls()

        group_schema = ExportGroupSchema(
            path=MAIN_TABLE,
            last_occurrences={app_id: app_version} if app_id else {},
        )

        for case_type, case_properties in case_property_mapping.items():

            for prop in case_properties:
                group_schema.items.append(ScalarItem(
                    path=[PathNode(name=prop)],
                    label=prop,
                    last_occurrences={app_id: app_version} if app_id else {},
                ))

        if parent_types:
            for case_type, identifier in parent_types:
                group_schema.items.append(CaseIndexItem(
                    path=[PathNode(name='indices'), PathNode(name=case_type)],
                    label='{}.{}'.format(identifier, case_type),
                    last_occurrences={app_id: app_version} if app_id else {},
                    tag=PROPERTY_TAG_CASE,
                ))

        schema.group_schemas.append(group_schema)
        return schema

    @classmethod
    def _generate_schema_for_parent_case(cls, app_id, app_version):
        """This is just a placeholder to indicate that the case has 'parents'.
        The actual schema is static so not stored in the DB.
        See ``corehq.apps.export.system_properties.PARENT_CASE_TABLE_PROPERTIES``
        """
        schema = cls()
        schema.group_schemas.append(ExportGroupSchema(
            path=PARENT_CASE_TABLE,
            last_occurrences={app_id: app_version},
        ))
        return schema

    @classmethod
    def _generate_schema_for_case_history(cls, case_property_mapping, app_id, app_version):
        """Generates the schema for the Case History tab on the export page.

        See ``corehq.apps.export.system_properties.CASE_HISTORY_PROPERTIES`` for
        additional 'static' schema items.
        """
        assert len(list(case_property_mapping)) == 1
        schema = cls()

        group_schema = ExportGroupSchema(
            path=CASE_HISTORY_TABLE,
            last_occurrences={app_id: app_version},
        )
        unknown_case_properties = set(case_property_mapping[list(case_property_mapping)[0]])
        unknown_case_properties -= set(KNOWN_CASE_PROPERTIES)

        def _add_to_group_schema(group_schema, path_start, prop, app_id, app_version):
            group_schema.items.append(ScalarItem(
                path=CASE_HISTORY_TABLE + [path_start, PathNode(name=prop)],
                label=prop,
                tag=PROPERTY_TAG_UPDATE,
                last_occurrences={app_id: app_version},
            ))

        for prop in KNOWN_CASE_PROPERTIES:
            path_start = PathNode(name="updated_known_properties")
            _add_to_group_schema(group_schema, path_start, prop, app_id, app_version)

        for prop in unknown_case_properties:
            path_start = PathNode(name="updated_unknown_properties")
            _add_to_group_schema(group_schema, path_start, prop, app_id, app_version)

        schema.group_schemas.append(group_schema)
        return schema

    @classmethod
    def _process_apps_for_export(cls, domain, schema, identifier, app_build_ids, task):
        if identifier == ALL_CASE_TYPE_EXPORT:
            return cls._process_apps_for_bulk_export(domain, schema, app_build_ids, task)
        else:
            return super(CaseExportDataSchema, cls)._process_apps_for_export(
                domain,
                schema,
                identifier,
                app_build_ids,
                task
            )

    @classmethod
    def _process_apps_for_bulk_export(cls, domain, schema, app_build_ids, task):
        schema.group_schemas = []
        apps_processed = 0
        case_types_to_use = get_case_types_for_domain(domain)
        for case_type in case_types_to_use:
            case_type_schema = cls()
            for app_doc in iter_docs(Application.get_db(), app_build_ids, chunksize=10):
                doc_type = app_doc.get('doc_type', '')
                if doc_type not in ('Application', 'LinkedApplication', 'Application-Deleted'):
                    continue
                if (not app_doc.get('has_submissions', False)
                        and app_doc.get('copy_of')):
                    continue

                app = Application.wrap(app_doc)
                try:
                    case_type_schema = cls._process_app_build(
                        case_type_schema,
                        app,
                        case_type,
                    )
                except Exception as e:
                    logging.exception('Failed to process app {}. {}'.format(app._id, e))
                    continue

            # If doing a bulk case export, we need to update the path of the group schemas to reflect
            # which case type they are linked to.
            for group_schema in case_type_schema.group_schemas:
                if group_schema.path == MAIN_TABLE:
                    group_schema.path = [PathNode(name=case_type), PathNode(name=ALL_CASE_TYPE_EXPORT)]
            schema.group_schemas += case_type_schema.group_schemas

            # Only record the version of builds on the schema. We don't care about
            # whether or not the schema has seen the current build because that always
            # gets processed.
            if app.copy_of:
                schema.record_update(app.copy_of, app.version)

            apps_processed += 1
            set_task_progress(task, apps_processed, len(app_build_ids) * len(case_types_to_use))

        return schema


class SMSExportDataSchema(ExportDataSchema):
    include_metadata = BooleanProperty(default=False)

    @property
    def type(self):
        return SMS_EXPORT

    @classmethod
    def generate_schema(cls, domain, app_id, identifier, force_rebuild=False,
                        only_process_current_builds=False, task=None):
        return cls(domain=domain)

    @classmethod
    def schema_version(cls):
        return SMS_DATA_SCHEMA_VERSION

    @staticmethod
    def get_latest_export_schema(domain, include_metadata, identifier=None):
        return SMSExportDataSchema(domain=domain, include_metadata=include_metadata)

    def _process_apps_for_export(cls, domain, schema, identifier, app_build_ids, task):
        return super(FormExportDataSchema, cls)._process_apps_for_export(
            domain,
            schema,
            identifier,
            app_build_ids,
            task
        )


def _string_path_to_list(path):
    return path if path is None else path[1:].split('/')


def _question_path_to_path_nodes(string_path, repeats):
    """
    Return a list of PathNodes suitable for a TableConfiguration or ExportGroupSchema
    path, from the given path and list of repeats.
    :param string_path: A path to a question or group, like "/data/group1"
    :param repeats: A list of repeat groups, like ["/data/repeat1"]
    :return: A list of PathNodes
    """
    if not string_path:
        return []

    parts = string_path.split("/")
    assert parts[0] == "", 'First part of path should be ""'
    parts = parts[1:]

    repeat_test_string = ""
    path = []
    for part in parts:
        repeat_test_string += "/" + part
        path.append(PathNode(name=part, is_repeat=repeat_test_string in repeats))

    path[0].name = "form"
    return path


def _path_nodes_to_string(path, separator=' '):
    if not path or (len(path) == 1 and path[0] is None):
        return ''
    return separator.join(["{}.{}".format(node.name, node.is_repeat) for node in path])


def _merge_lists(one, two, keyfn, resolvefn):
    """Merges two lists. The algorithm is to first iterate over the first list. If the item in the first list
    does not exist in the second list, add that item to the merged list. If the item does exist in the second
    list, resolve the conflict using the resolvefn. After the first list has been iterated over, simply append
    any items in the second list that have not already been added. If the items in the list are objects,
    then the objects will be mutated directly and not copied.

    :param one: The first list to be merged.
    :param two: The second list to be merged.
    :param keyfn: A function that takes an element from the list as an argument and returns a unique
        identifier for that item.
    :param resolvefn: A function that takes two elements that resolve to the same key and returns a single
        element that has resolved the conflict between the two elements.
    :returns: A list of the merged elements
    """

    merged = []

    two_keys = {keyfn(obj): obj for obj in two}

    for obj in one:
        obj_key = keyfn(obj)

        if obj_key in two_keys:
            # If obj exists in both list, must merge
            new_obj = resolvefn(
                obj,
                two_keys.pop(obj_key),
            )
        else:
            new_obj = obj

        merged.append(new_obj)

    # Get the rest of the objects in the second list
    merged.extend(list(two_keys.values()))
    return merged


def _merge_dicts(one, two):
    """Merges two dicts. The algorithm is to first create a dictionary of all the keys that exist in one and
    two but not in both. Then iterate over each key that belongs in both, selecting the one with the higher value.

    :param one: The first dictionary
    :param two: The second dictionary
    :returns: The merged dictionary
    """
    # keys either in one or two, but not both
    merged = {
        key: one.get(key, two.get(key))
        for key in one.keys() ^ two.keys()
    }

    def resolvefn(a, b):
        if a is None:
            return b

        if b is None:
            return a

        return max(a, b)

    # merge keys that exist in both
    merged.update({
        key: resolvefn(one[key], two[key])
        for key in one.keys() & two.keys()
    })
    return merged


class UserDefinedExportColumn(ExportColumn):
    """
    This model represents a column that a user has defined the path to the
    data within the form. It should only be needed for RemoteApps
    """

    is_editable = BooleanProperty(default=True)

    # On normal columns, the path is defined on an ExportItem.
    # Since a UserDefinedExportColumn is not associated with the
    # export schema, the path is defined on the column.
    custom_path = SchemaListProperty(PathNode)

    def get_value(self, domain, doc_id, doc, base_path, **kwargs):
        path = [x.name for x in self.custom_path[len(base_path):]]
        return NestedDictGetter(path)(doc)


class SplitUserDefinedExportColumn(ExportColumn):
    split_type = StringProperty(
        choices=USER_DEFINED_SPLIT_TYPES,
        default=PLAIN_USER_DEFINED_SPLIT_TYPE
    )
    user_defined_options = ListProperty()

    def get_value(self, domain, doc_id, doc, base_path, transform_dates=False, **kwargs):
        """
        Get the value of self.item of the given doc.
        When base_path is [], doc is a form submission or case,
        when base_path is non empty, doc is a repeat group from a form submission.
        doc is a form submission or instance of a repeat group in a submission or case
        """
        value = super(SplitUserDefinedExportColumn, self).get_value(
            domain,
            doc_id,
            doc,
            base_path,
            transform_dates=transform_dates
        )
        if self.split_type == PLAIN_USER_DEFINED_SPLIT_TYPE:
            return value

        if not isinstance(value, str):
            return [None] * len(self.user_defined_options) + [value]

        selected = OrderedDict((x, 1) for x in value.split(" "))
        row = []
        for option in self.user_defined_options:
            row.append(selected.pop(option, None))
        row.append(" ".join(selected))
        return row

    def get_headers(self, **kwargs):
        if self.split_type == PLAIN_USER_DEFINED_SPLIT_TYPE:
            return super(SplitUserDefinedExportColumn, self).get_headers()
        header = self.label
        header_template = header if '{option}' in header else "{name} | {option}"
        headers = []
        for option in self.user_defined_options:
            headers.append(
                header_template.format(
                    name=header,
                    option=option
                )
            )
        headers.append(
            header_template.format(
                name=header,
                option='extra'
            )
        )
        return headers


class MultiMediaExportColumn(ExportColumn):
    """
    A column that will take a multimedia file and transform it to the absolute download URL.
    If transform_dates is set to True it will render the link with Excel formatting
    in order to make the link clickable.
    """

    def get_value(self, domain, doc_id, doc, base_path, transform_dates=False, **kwargs):
        value = super(MultiMediaExportColumn, self).get_value(domain, doc_id, doc, base_path, **kwargs)

        if (not value
                or value == MISSING_VALUE
                or value not in doc.get('external_blobs', {})):
            return value

        download_url = absolute_reverse('api_form_attachment', args=(domain, doc_id, value))
        if transform_dates:
            download_url = '=HYPERLINK("{}")'.format(download_url)

        return download_url


class SplitGPSExportColumn(ExportColumn):
    item = SchemaProperty(GeopointItem)

    def get_headers(self, split_column=False):
        if not split_column:
            return super(SplitGPSExportColumn, self).get_headers()
        header = self.label
        header_templates = [
            _('{}: latitude (degrees)'),
            _('{}: longitude (degrees)'),
            _('{}: altitude (meters)'),
            _('{}: accuracy (meters)'),
        ]
        return [header_template.format(header) for header_template in header_templates]

    def get_value(self, domain, doc_id, doc, base_path, split_column=False, **kwargs):
        coord_string = super().get_value(
            domain,
            doc_id,
            doc,
            base_path,
            **kwargs
        )
        if not split_column:
            return coord_string

        return self.extract_coordinate_array(coord_string)

    @classmethod
    def extract_coordinate_array(cls, coord_string):
        NUM_VALUES = 4

        if coord_string == MISSING_VALUE:
            return [MISSING_VALUE] * NUM_VALUES

        values = [EMPTY_VALUE] * NUM_VALUES
        if not isinstance(coord_string, str):
            return values

        for index, coordinate in enumerate(coord_string.split()):
            # NOTE: Unclear if the intention here is to support situations where only the lat/lng are supplied,
            # or if we really want to allow just specifying just lat, or lat/lng/alt as valid.
            # I think it's likely we only want to support the lat/lng situation, but leaving as is
            # in the event that this behavior is relied upon somewhere
            if index >= NUM_VALUES:
                break
            values[index] = coordinate

        return values


class SplitExportColumn(ExportColumn):
    """
    This class is used to split a value into multiple columns based
    on a set of pre-defined options. It splits the data value assuming it
    is space separated.

    The outputs will have one column for each 'option' and one additional
    column for any values from the data don't appear in the options.

    Each column will have a value of 1 if the data value contains the
    option for that column otherwise the column will be blank.

    e.g.
    options = ['a', 'b']
    column_headers = ['col a', 'col b', 'col extra']

    data_val = 'a c d'
    output = [1, '', 'c d']

    Note: when split_column is set to False, SplitExportColumn will behave like a
    normal ExportColumn.
    """
    item = SchemaProperty(MultipleChoiceItem)
    ignore_unspecified_options = BooleanProperty(default=False)

    def get_value(self, domain, doc_id, doc, base_path, split_column=False, **kwargs):
        """
        Get the value of self.item of the given doc.
        When base_path is [], doc is a form submission or case,
        when base_path is non empty, doc is a repeat group from a form submission.
        doc is a form submission or instance of a repeat group in a submission or case
        """
        value = super(SplitExportColumn, self).get_value(domain, doc_id, doc, base_path, **kwargs)
        if not split_column:
            return value

        if value == MISSING_VALUE:
            value = [MISSING_VALUE] * len(self.item.options)
            if not self.ignore_unspecified_options:
                value.append(MISSING_VALUE)
            return value

        if not isinstance(value, str):
            unspecified_options = [] if self.ignore_unspecified_options else [value]
            return [EMPTY_VALUE] * len(self.item.options) + unspecified_options

        selected = OrderedDict((x, 1) for x in value.split(" "))
        row = []
        for option in self.item.options:
            row.append(selected.pop(option.value, EMPTY_VALUE))
        if not self.ignore_unspecified_options:
            row.append(" ".join(selected))
        return row

    def get_headers(self, split_column=False):
        if not split_column:
            return super(SplitExportColumn, self).get_headers()
        header = self.label
        header_template = header if '{option}' in header else "{name} | {option}"
        headers = []
        for option in self.item.options:
            headers.append(
                header_template.format(
                    name=header,
                    option=option.value
                )
            )
        if not self.ignore_unspecified_options:
            headers.append(
                header_template.format(
                    name=header,
                    option='extra'
                )
            )
        return headers


class RowNumberColumn(ExportColumn):
    """
    This column represents the `number` column.
    """
    repeat = IntegerProperty(default=0)

    def get_headers(self, **kwargs):
        headers = [self.label]
        if self.repeat > 0:
            headers += ["{}__{}".format(self.label, i) for i in range(self.repeat + 1)]
        return headers

    def get_value(self, domain, doc_id, doc, base_path, transform_dates=False, row_index=None, **kwargs):
        assert row_index, 'There must be a row_index for number column'
        return (
            [".".join([str(i) for i in row_index])]
            + (list(row_index) if len(row_index) > 1 else [])
        )

    def update_nested_repeat_count(self, repeat):
        self.repeat = repeat


class CaseIndexExportColumn(ExportColumn):
    """
    A column that exports a case index's referenced ids
    """

    def get_value(self, domain, doc_id, doc, base_path, **kwargs):
        path = [self.item.path[0].name]  # Index columns always are just a reference to 'indices'
        case_type = self.item.case_type

        indices = NestedDictGetter(path)(doc) or []
        case_ids = [index.get('referenced_id') for index in indices if index.get('referenced_type') == case_type]
        return ' '.join(case_ids)


class StockFormExportColumn(ExportColumn):
    """
    A column type for stock question types in form exports. This will export a column
    for a StockItem
    """

    def get_value(self, domain, doc_id, doc, base_path, transform_dates=False, **kwargs):

        stock_type_path_index = -1
        path = [path_node.name for path_node in self.item.path[len(base_path):]]
        # Hacky, but the question_id is encoded in the path of the StockItem.
        # Normally, stock questions (balance, transfer, receive, dispense) do
        # not include the question id in the form xml path. For example the defintion
        # of a stock question can look like this:
        #
        # <transfer date="2016-08-08" dest="xxxx" section-id="xxxx" type="question-id">
        #     <n0:entry id="xxxx" quantity="1"/>
        # </transfer>
        #
        # Notice that the question id is stored in the type attribute. If multiple
        # stock questions are defined at the same level in the tree, the form processing
        # code will interpret this as a "repeat" leading to confusion for the user in the
        # export code.
        #
        # In order to mitigate this, we encode the question id into the path so we do not
        # have to create a new TableConfiguration for the edge case mentioned above.
        for idx, path_name in enumerate(path):
            is_stock_question_element = any(
                [path_name.startswith('{}:'.format(tag_name)) for tag_name in STOCK_QUESTION_TAG_NAMES]
            )
            if is_stock_question_element:
                question_path, question_id = path_name.split(':')
                path[idx] = question_path
                stock_type_path_index = idx
                break

        value = NestedDictGetter(path[:stock_type_path_index + 1])(doc)
        if not value:
            return MISSING_VALUE

        new_doc = None
        if isinstance(value, list):
            try:
                new_doc = list(filter(
                    lambda node: node.get('@type') == question_id,
                    value,
                ))[0]
            except IndexError:
                new_doc = None
        else:
            if value.get('@type') == question_id:
                new_doc = value

        if not new_doc:
            return MISSING_VALUE

        return self._transform(
            NestedDictGetter(path[stock_type_path_index + 1:])(new_doc),
            new_doc,
            transform_dates
        )


class StockExportColumn(ExportColumn):
    """
    A special column type for case exports. This will export a column
    for each product/section combo on the provided domain. (A lot of this code is taken
    from corehq/apps/commtrack/models.py#StockExportColumn
    """
    domain = StringProperty()

    @property
    def accessor(self):
        return LedgerAccessors(self.domain)

    def update_domain(self, domain):
        self.domain = domain

    @property
    @memoized
    def _column_tuples(self):
        return get_ledger_section_entry_combinations(self.domain)

    def _get_product_name(self, product_id):
        try:
            return SQLProduct.objects.values_list('name', flat=True).get(product_id=product_id, domain=self.domain)
        except SQLProduct.DoesNotExist:
            return product_id

    def get_headers(self, **kwargs):
        return [
            "{product} ({section})".format(
                product=self._get_product_name(product_id),
                section=section
            )
            for product_id, section in self._column_tuples
        ]

    def get_value(self, domain, doc_id, doc, base_path, **kwargs):
        states = self.accessor.get_ledger_values_for_case(doc_id)

        # use a list to make sure the stock states end up
        # in the same order as the headers
        values = [EMPTY_VALUE] * len(self._column_tuples)

        for state in states:
            column_tuple = (state.product_id, state.section_id)
            if column_tuple in self._column_tuples:
                state_index = self._column_tuples.index(column_tuple)
                values[state_index] = state.stock_on_hand
        return values


def _meta_property(name):
    def fget(self):
        return getattr(self._meta, name)
    return property(fget)


class DataFile(object):
    """DataFile is a thin wrapper around BlobMeta"""
    id = _meta_property("id")
    domain = _meta_property("parent_id")
    filename = _meta_property("name")
    blob_id = _meta_property("key")
    content_type = _meta_property("content_type")
    content_length = _meta_property("content_length")
    delete_after = _meta_property("expires_on")

    def __init__(self, meta):
        self._meta = meta

    @property
    def description(self):
        return self._meta.properties["description"]

    @classmethod
    def get(cls, domain, pk):
        return cls(cls.meta_query(domain).get(pk=pk))

    @staticmethod
    def meta_query(domain):
        Q = models.Q
        return BlobMeta.objects.partitioned_query(domain).filter(
            Q(expires_on__isnull=True) | Q(expires_on__gte=datetime.utcnow()),
            parent_id=domain,
            type_code=CODES.data_file,
        )

    @classmethod
    def get_all(cls, domain):
        return [cls(meta) for meta in cls.meta_query(domain).order_by("name")]

    @classmethod
    def get_total_size(cls, domain):
        return cls.meta_query(domain).aggregate(total=Sum('content_length'))["total"]

    @classmethod
    def save_blob(cls, file_obj, domain, filename, description, content_type, delete_after):
        if delete_after is None:
            raise ValidationError(
                'delete_after can be None only for legacy files that were added before August 2018'
            )
        return cls(get_blob_db().put(
            file_obj,
            domain=domain,
            parent_id=domain,
            type_code=CODES.data_file,
            name=filename,
            key=random_url_id(16),
            content_type=content_type,
            expires_on=delete_after,
            properties={"description": description},
        ))

    def get_blob(self):
        db = get_blob_db()
        try:
            blob = db.get(meta=self._meta)
        except (KeyError, NotFound) as err:
            raise NotFound(str(err))
        return blob

    def delete(self):
        get_blob_db().delete(key=self._meta.key)

    DoesNotExist = BlobMeta.DoesNotExist


class EmailExportWhenDoneRequest(models.Model):
    domain = models.CharField(max_length=255)
    download_id = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)


class LedgerSectionEntry(models.Model):
    domain = models.CharField(max_length=255)
    section_id = models.CharField(max_length=255)
    entry_id = models.CharField(max_length=255)

    class Meta(object):
        unique_together = ('domain', 'section_id', 'entry_id')


def get_ledger_section_entry_combinations(domain):
    return list(
        LedgerSectionEntry.objects
        .filter(domain=domain)
        .order_by('entry_id', 'section_id')
        .values_list('entry_id', 'section_id')
        .all()
    )


# These must match the constants in corehq/apps/export/static/export/js/const.js
MAIN_TABLE = []
CASE_HISTORY_TABLE = [PathNode(name='actions', is_repeat=True)]
PARENT_CASE_TABLE = [PathNode(name='indices', is_repeat=True)]

# Used to identify tables in a bulk case export
ALL_CASE_TYPE_TABLE = PathNode(name=ALL_CASE_TYPE_EXPORT)


def datasource_export_instance(config):
    adapter = get_indicator_adapter(config)
    table = adapter.get_table()

    def get_export_column(column):
        return ExportColumn(
            label=column.id,
            item=ExportItem(
                path=[PathNode(name=column.id)],
                label=column.id,
                datatype=column.datatype,
            ),
            selected=True,
        )

    # table.name follows this format: ucr_{project space}_{table id}_{unique hash}
    unique_hash = table.name.split("_")[-1]
    sheet_name = adapter.table_id
    if len(sheet_name) > EXCEL_MAX_SHEET_NAME_LENGTH:
        sheet_name = f"{config.domain}_{unique_hash}"
        if len(sheet_name) > EXCEL_MAX_SHEET_NAME_LENGTH:
            sheet_name = unique_hash

    return DataSourceExportInstance(
        name=config.display_name,
        domain=config.domain,
        tables=[
            TableConfiguration(
                label=sheet_name,
                columns=[
                    get_export_column(col)
                    for col in config.columns_by_id.values()
                ],
            )
        ],
        data_source_id=config.data_source_id,
    )
