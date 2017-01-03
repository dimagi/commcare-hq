from copy import copy
from datetime import datetime
from itertools import groupby
from functools import partial
from collections import defaultdict, OrderedDict, namedtuple

from couchdbkit import ResourceConflict
from couchdbkit.ext.django.schema import IntegerProperty
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse

from corehq.apps.export.esaccessors import get_ledger_section_entry_combinations
from dimagi.utils.decorators.memoized import memoized
from couchdbkit import SchemaListProperty, SchemaProperty, BooleanProperty, DictProperty

from corehq import feature_previews
from corehq.apps.userreports.expressions.getters import NestedDictGetter
from corehq.apps.app_manager.const import STOCK_QUESTION_TAG_NAMES
from corehq.apps.app_manager.dbaccessors import (
    get_built_app_ids_with_submissions_for_app_id,
    get_all_built_app_ids_and_versions,
    get_latest_app_ids_and_versions,
    get_app_ids_in_domain,
)
from corehq.apps.app_manager.models import Application, AdvancedFormActions
from corehq.apps.app_manager.util import get_case_properties, ParentCasePropertyBuilder
from corehq.apps.domain.models import Domain
from corehq.apps.products.models import Product
from corehq.apps.reports.display import xmlns_to_name
from corehq.blobs.mixin import BlobMixin
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.util.global_request import get_request
from corehq.util.view_utils import absolute_reverse
from couchexport.models import Format
from couchexport.transforms import couch_to_excel_datetime
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.web import get_url_base
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    ListProperty,
    StringProperty,
    DateTimeProperty,
    SetProperty,
)
from corehq.apps.export.const import (
    PROPERTY_TAG_UPDATE,
    PROPERTY_TAG_DELETED,
    FORM_EXPORT,
    CASE_EXPORT,
    TRANSFORM_FUNCTIONS,
    DEID_TRANSFORM_FUNCTIONS,
    PROPERTY_TAG_CASE,
    USER_DEFINED_SPLIT_TYPES,
    PLAIN_USER_DEFINED_SPLIT_TYPE,
    CASE_DATA_SCHEMA_VERSION,
    FORM_DATA_SCHEMA_VERSION,
    MISSING_VALUE,
    EMPTY_VALUE,
    KNOWN_CASE_PROPERTIES,
    CASE_ATTRIBUTES,
    CASE_CREATE_ELEMENTS,
    UNKNOWN_INFERRED_FROM,
)
from corehq.apps.export.exceptions import BadExportConfiguration
from corehq.apps.export.dbaccessors import (
    get_latest_case_export_schema,
    get_latest_form_export_schema,
    get_inferred_schema,
)
from corehq.apps.export.utils import is_occurrence_deleted


DAILY_SAVED_EXPORT_ATTACHMENT_NAME = "payload"


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

    def __eq__(self, other):
        return (
            type(self) == type(other) and
            self.doc_type == other.doc_type and
            self.name == other.name and
            self.is_repeat == other.is_repeat
        )


class ExportItem(DocumentSchema):
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
    transform = StringProperty(choices=TRANSFORM_FUNCTIONS.keys())

    # True if this item was inferred from different actions in HQ (i.e. case upload)
    # False if the item was found in the application structure
    inferred = BooleanProperty(default=False)
    inferred_from = SetProperty(default=set)

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
            label=question['label'],
            last_occurrences={app_id: app_version},
        )

    @classmethod
    def merge(cls, one, two):
        item = one
        item.last_occurrences = _merge_dicts(one.last_occurrences, two.last_occurrences, max)
        item.inferred = one.inferred or two.inferred
        item.inferred_from |= two.inferred_from
        return item

    @property
    def readable_path(self):
        return '.'.join(map(lambda node: node.name, self.path))


class ExportColumn(DocumentSchema):
    """
    The model that represents a column in an export. Each column has a one-to-one
    mapping with an ExportItem. The column controls the presentation of that item.
    """

    item = SchemaProperty(ExportItem)
    label = StringProperty()
    # Determines whether or not to show the column in the UI Config without clicking advanced
    is_advanced = BooleanProperty(default=False)
    selected = BooleanProperty(default=False)
    tags = ListProperty()
    help_text = StringProperty()

    # A transforms that deidentifies the value
    deid_transform = StringProperty(choices=DEID_TRANSFORM_FUNCTIONS.keys())

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
        if isinstance(value, dict) and '#text' in value:
            value = value.get('#text')

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
        return value

    @staticmethod
    def create_default_from_export_item(table_path, item, app_ids_and_versions, auto_select=True):
        """Creates a default ExportColumn given an item

        :param table_path: The path of the table_path that the item belongs to
        :param item: An ExportItem instance
        :param app_ids_and_versions: A dictionary of app ids that map to latest build version
        :param auto_select: Automatically select the column
        :returns: An ExportColumn instance
        """
        is_case_update = item.tag == PROPERTY_TAG_CASE and not isinstance(item, CaseIndexItem)
        is_case_history_update = item.tag == PROPERTY_TAG_UPDATE
        is_label_question = isinstance(item, LabelItem)

        is_main_table = table_path == MAIN_TABLE
        constructor_args = {
            "item": item,
            "label": item.readable_path if not is_case_history_update else item.label,
            "is_advanced": is_case_update or is_label_question,
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
                help_text=_(u'The ID of the associated {} case type').format(item.case_type),
                **constructor_args
            )
        elif get_request() and feature_previews.SPLIT_MULTISELECT_CASE_EXPORT.enabled(get_request().domain):
            column = SplitUserDefinedExportColumn(**constructor_args)
        else:
            column = ExportColumn(**constructor_args)
        column.update_properties_from_app_ids_and_versions(app_ids_and_versions)
        column.selected = (
            auto_select and
            not column._is_deleted(app_ids_and_versions) and
            not is_case_update and
            not is_label_question and
            is_main_table
        )
        return column

    def _is_deleted(self, app_ids_and_versions):
        return (
            is_occurrence_deleted(self.item.last_occurrences, app_ids_and_versions) and
            not self.item.inferred
        )

    def update_properties_from_app_ids_and_versions(self, app_ids_and_versions):
        """
        This regenerates properties based on new build ids/versions
        :param app_ids_and_versions: A dictionary of app ids that map to latest build version
        most recent state of the app(s) in the domain
        """
        is_deleted = self._is_deleted(app_ids_and_versions)

        tags = []
        if is_deleted:
            tags.append(PROPERTY_TAG_DELETED)

        if self.item.tag:
            tags.append(self.item.tag)
        self.is_advanced = is_deleted or self.is_advanced
        self.tags = tags

    @property
    def is_deidentifed(self):
        return bool(self.deid_transform)

    def get_headers(self, split_column=False):
        if self.is_deidentifed:
            return [u"{} {}".format(self.label, "[sensitive]")]
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


class TableConfiguration(DocumentSchema):
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

    def get_rows(self, document, row_number, split_columns=False, transform_dates=False):
        """
        Return a list of ExportRows generated for the given document.
        :param document: dictionary representation of a form submission or case
        :param row_number: number indicating this documents index in the sequence of all documents in the export
        :return: List of ExportRows
        """
        sub_documents = self._get_sub_documents(document, row_number)

        domain = document.get('domain')
        document_id = document.get('_id')

        assert domain is not None, 'Form or Case must be associated with domain'
        assert document_id is not None, 'Form or Case must have an id'

        rows = []
        for doc_row in sub_documents:
            doc, row_index = doc_row.doc, doc_row.row

            row_data = []
            for col in self.selected_columns:
                val = col.get_value(
                    domain,
                    document_id,
                    doc,
                    self.path,
                    row_index=row_index,
                    split_column=split_columns,
                    transform_dates=transform_dates,
                )
                if isinstance(val, list):
                    row_data.extend(val)
                else:
                    row_data.append(val)
            rows.append(ExportRow(data=row_data))
        return rows

    def get_column(self, item_path, item_doc_type, column_transform):
        """
        Given a path and transform, will return the column and its index. If not found, will
        return None, None

        :param item_path: A list of path nodes that identify a column
        :param item_doc_type: The doc type of the item (often just ExportItem). If getting
                UserDefinedExportColumn, set this to None
        :param column_transform: A transform that is applied on the column
        :returns index, column: The index of the column in the list and an ExportColumn
        """
        for index, column in enumerate(self.columns):
            if (column.item.path == item_path and
                    column.item.transform == column_transform and
                    column.item.doc_type == item_doc_type):
                return index, column
            # No item doc type searches for a UserDefinedExportColumn
            elif (isinstance(column, UserDefinedExportColumn) and
                    column.custom_path == item_path and
                    item_doc_type is None):
                return index, column
        return None, None

    def _get_sub_documents(self, document, row_number):
        return self._get_sub_documents_helper(self.path, [DocRow(row=(row_number,), doc=document)])

    @staticmethod
    def _get_sub_documents_helper(path, row_docs):
        """
        Return each instance of a repeat group at the path from the given docs.
        If path is [], just return the docs

        See corehq.apps.export.tests.test_table_configuration.TableConfigurationGetRowsTest.test_get_sub_documents
        for examples

        :param path: A list of a strings
        :param docs: A list of dicts representing form submissions
        :return:
        """
        if len(path) == 0:
            return row_docs

        new_docs = []
        for row_doc in row_docs:
            doc = row_doc.doc
            row_index = row_doc.row

            next_doc = doc.get(path[0].name, {})
            if path[0].is_repeat:
                if type(next_doc) != list:
                    # This happens when a repeat group has a single repeat iteration
                    next_doc = [next_doc]
                new_docs.extend([
                    DocRow(row=row_index + (new_doc_index,), doc=new_doc)
                    for new_doc_index, new_doc in enumerate(next_doc)
                ])
            elif next_doc:
                new_docs.append(DocRow(row=row_index, doc=next_doc))
        return TableConfiguration._get_sub_documents_helper(path[1:], new_docs)


class ExportInstance(BlobMixin, Document):
    """
    This is an instance of an export. It contains the tables to export and
    other presentation properties.
    """

    name = StringProperty()
    domain = StringProperty()
    tables = ListProperty(TableConfiguration)
    export_format = StringProperty(default='csv')

    # Whether to split multiselects into multiple columns
    split_multiselects = BooleanProperty(default=False)

    # Whether to automatically convert dates to excel dates
    transform_dates = BooleanProperty(default=True)

    # Whether the export is de-identified
    is_deidentified = BooleanProperty(default=False)

    # Keep reference to old schema id if we have converted it from the legacy infrastructure
    legacy_saved_export_schema_id = StringProperty()

    is_daily_saved_export = BooleanProperty(default=False)
    # daily saved export fields:
    last_updated = DateTimeProperty()
    last_accessed = DateTimeProperty()

    class Meta:
        app_label = 'export'

    @property
    def is_safe(self):
        """For compatibility with old exports"""
        return self.is_deidentified

    @property
    def defaults(self):
        return FormExportInstanceDefaults if self.type == FORM_EXPORT else CaseExportInstanceDefaults

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
        return filter(lambda t: t.selected, self.tables)

    def get_table(self, path):
        for table in self.tables:
            if table.path == path:
                return table
        return None

    @classmethod
    def _new_from_schema(cls, schema):
        raise NotImplementedError()

    @classmethod
    def generate_instance_from_schema(cls, schema, saved_export=None, auto_select=True):
        """Given an ExportDataSchema, this will generate an ExportInstance"""
        if saved_export:
            instance = saved_export
        else:
            instance = cls._new_from_schema(schema)

        instance.name = instance.name or instance.defaults.get_default_instance_name(schema)

        latest_app_ids_and_versions = get_latest_app_ids_and_versions(
            schema.domain,
            getattr(schema, 'app_id', None),
        )
        group_schemas = schema.group_schemas

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
                if not column:
                    column = ExportColumn.create_default_from_export_item(
                        table.path,
                        item,
                        latest_app_ids_and_versions,
                        auto_select
                    )
                    if prev_index:
                        # if it's a new column, insert it right after the previous column
                        index = prev_index + 1
                        table.columns.insert(index, column)
                    else:
                        table.columns.append(column)

                # Ensure that the item is up to date
                column.item = item

                # Need to rebuild tags and other flags based on new build ids
                column.update_properties_from_app_ids_and_versions(latest_app_ids_and_versions)
                prev_index = index

            cls._insert_system_properties(instance.domain, schema.type, table)

            if not instance.get_table(group_schema.path):
                instance.tables.append(table)

        return instance

    @classmethod
    def _insert_system_properties(cls, domain, export_type, table):
        from corehq.apps.export.system_properties import (
            ROW_NUMBER_COLUMN,
            TOP_MAIN_FORM_TABLE_PROPERTIES,
            BOTTOM_MAIN_FORM_TABLE_PROPERTIES,
            TOP_MAIN_CASE_TABLE_PROPERTIES,
            BOTTOM_MAIN_CASE_TABLE_PROPERTIES,
            CASE_HISTORY_PROPERTIES,
            PARENT_CASE_TABLE_PROPERTIES,
            STOCK_COLUMN,
        )

        nested_repeat_count = len([node for node in table.path if node.is_repeat])
        column_initialization_data = {
            'repeat': nested_repeat_count,  # Used for determining the proper row column
            'domain': domain,  # Used for the StockExportColumn
        }
        if export_type == FORM_EXPORT:
            if table.path == MAIN_TABLE:
                cls.__insert_system_properties(
                    table,
                    TOP_MAIN_FORM_TABLE_PROPERTIES,
                    **column_initialization_data
                )
                cls.__insert_system_properties(
                    table,
                    BOTTOM_MAIN_FORM_TABLE_PROPERTIES,
                    top=False,
                    **column_initialization_data
                )
            else:
                cls.__insert_system_properties(table, [ROW_NUMBER_COLUMN], **column_initialization_data)
        elif export_type == CASE_EXPORT:
            if table.path == MAIN_TABLE:
                if Domain.get_by_name(domain).commtrack_enabled:
                    top_properties = TOP_MAIN_CASE_TABLE_PROPERTIES + [STOCK_COLUMN]
                else:
                    top_properties = TOP_MAIN_CASE_TABLE_PROPERTIES
                cls.__insert_system_properties(
                    table,
                    top_properties,
                    **column_initialization_data
                )
                cls.__insert_system_properties(
                    table,
                    BOTTOM_MAIN_CASE_TABLE_PROPERTIES,
                    top=False,
                    **column_initialization_data
                )
            elif table.path == CASE_HISTORY_TABLE:
                cls.__insert_system_properties(table, CASE_HISTORY_PROPERTIES, **column_initialization_data)
            elif table.path == PARENT_CASE_TABLE:
                cls.__insert_system_properties(table, PARENT_CASE_TABLE_PROPERTIES,
                        **column_initialization_data)

    @classmethod
    def __insert_system_properties(cls, table, properties, top=True, **column_initialization_data):
        """
        Inserts system properties into the table configuration

        :param table: A TableConfiguration instance
        :param properties: A list of ExportColumn that represent system properties to be added to the table
        :param top: When True inserts the columns at the top, when false at the bottom
        :param column_initialization_data: Extra data to be passed to the column if needed on initialization
        """
        properties = map(copy, properties)
        if top:
            insert_fn = partial(table.columns.insert, 0)
            properties = reversed(properties)
        else:
            insert_fn = table.columns.append

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
                column.update_domain(column_initialization_data.get('domain'))

            if not existing_column:
                insert_fn(static_column)

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


class CaseExportInstance(ExportInstance):
    case_type = StringProperty()
    type = CASE_EXPORT

    @classmethod
    def _new_from_schema(cls, schema):
        return cls(
            domain=schema.domain,
            case_type=schema.case_type,
        )


class FormExportInstance(ExportInstance):
    xmlns = StringProperty()
    app_id = StringProperty()
    type = FORM_EXPORT

    # Whether to include duplicates and other error'd forms in export
    include_errors = BooleanProperty(default=False)

    @property
    def formname(self):
        return xmlns_to_name(self.domain, self.xmlns, self.app_id)

    @classmethod
    def _new_from_schema(cls, schema):
        return cls(
            domain=schema.domain,
            xmlns=schema.xmlns,
            app_id=schema.app_id,
        )


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
        return path == MAIN_TABLE


class FormExportInstanceDefaults(ExportInstanceDefaults):

    @staticmethod
    def get_default_instance_name(schema):
        return u'{} ({})'.format(
            xmlns_to_name(schema.domain, schema.xmlns, schema.app_id, separator=" - "),
            datetime.now().strftime('%Y-%m-%d')
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
        else:
            return _('Unknown')

    @staticmethod
    def get_default_instance_name(schema):
        return u'{}: {}'.format(schema.case_type, datetime.now().strftime('%Y-%m-%d'))


class ExportRow(object):

    def __init__(self, data):
        self.data = data


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
    An item that refers to a case index
    """

    @property
    def case_type(self):
        return self.path[1].name


class GeopointItem(ExportItem):
    """
    A GPS coordinate question
    """


class MultiMediaItem(ExportItem):
    """
    An item that references multimedia
    """


class StockItem(ExportItem):
    """
    An item that references a stock question (balance, transfer, dispense, receive)
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
                    last_occurrences=_merge_dicts(option1.last_occurrences, option2.last_occurrences, max)
                ),
        )

        item.options = options
        return item


class ExportGroupSchema(DocumentSchema):
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
            label='.'.join(map(lambda node: node.name, path)),
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
    case_type = StringProperty(required=True)
    version = IntegerProperty(default=1)

    # This normally contains a mapping of app_id to the version number. For
    # inferred schemas this'll always be an empty dictionary since it is
    # inferred. It is needed because when schemas are merged, it's expected
    # that all schema duck types have this property.
    last_app_versions = DictProperty()

    class Meta:
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

    class Meta:
        app_label = 'export'

    @classmethod
    def generate_schema_from_builds(cls, domain, app_id, identifier, force_rebuild=False):
        """Builds a schema from Application builds for a given identifier

        :param domain: The domain that the export belongs to
        :param app_id: The app_id that the export belongs to (or None if export is not associated with an app.
        :param identifier: The unique identifier of the schema being exported.
            case_type for Case Exports and xmlns for Form Exports
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

        app_build_ids = cls._get_app_build_ids_to_process(
            domain,
            app_id,
            current_schema.last_app_versions,
        )
        if app_id:
            app_build_ids.append(app_id)
        else:
            app_build_ids.extend(cls._get_current_app_ids_for_domain(domain))

        for app_doc in iter_docs(Application.get_db(), app_build_ids, chunksize=10):
            if (not app_doc.get('has_submissions', False) and
                    app_doc.get('copy_of')):
                continue

            app = Application.wrap(app_doc)
            current_schema = cls._process_app_build(
                current_schema,
                app,
                identifier,
            )

            current_schema.record_update(app.copy_of or app._id, app.version)

        inferred_schema = cls._get_inferred_schema(domain, identifier)
        if inferred_schema:
            current_schema = cls._merge_schemas(current_schema, inferred_schema)

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
    def _merge_schemas(cls, *schemas):
        """Merges two ExportDataSchemas together

        :param schema1: The first ExportDataSchema
        :param schema2: The second ExportDataSchema
        :returns: The merged ExportDataSchema
        """

        schema = cls()

        def resolvefn(group_schema1, group_schema2):

            def keyfn(export_item):
                return'{}:{}:{}'.format(
                    _path_nodes_to_string(export_item.path),
                    export_item.doc_type,
                    export_item.transform,
                )

            group_schema1.last_occurrences = _merge_dicts(
                group_schema1.last_occurrences,
                group_schema2.last_occurrences,
                max
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
                current_schema.last_app_versions,
                max,
            )

        schema.group_schemas = group_schemas
        schema.last_app_versions = last_app_versions

        return schema

    def record_update(self, app_id, app_version):
        self.last_app_versions[app_id] = max(
            self.last_app_versions.get(app_id, 0),
            app_version,
        )

    @staticmethod
    def _save_export_schema(current_schema, original_id, original_rev):
        """
        Given a schema object, this function saves the object and ensures that the
        ID remains the save as the previous save if there existed a previous version.
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
    def _get_inferred_schema(cls, domain, xmlns):
        return None

    def _set_identifier(self, form_xmlns):
        self.xmlns = form_xmlns

    @classmethod
    def _get_current_app_ids_for_domain(cls, domain):
        raise BadExportConfiguration('Form exports should only use one app_id and this should not be called')

    @staticmethod
    def _get_app_build_ids_to_process(domain, app_id, last_app_versions):
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
        form = app.get_form_by_xmlns(form_xmlns, log_missing=False)
        if not form:
            return current_schema

        case_updates = form.get_case_updates(form.get_module().case_type)
        xform = form.wrapped_xform()
        if isinstance(form.actions, AdvancedFormActions):
            open_case_actions = form.actions.open_cases
        else:
            open_case_actions = form.actions.subcases

        repeats_with_subcases = {
            open_case_action for open_case_action in open_case_actions
            if open_case_action.repeat_context
        }
        xform_schema = cls._generate_schema_from_xform(
            xform,
            case_updates,
            app.langs,
            app.copy_of or app._id,  # If it's not a copy, must be current
            app.version,
        )
        schemas = [current_schema, xform_schema]
        if repeats_with_subcases:
            repeat_case_schema = cls._generate_schema_from_repeat_subcases(
                xform,
                repeats_with_subcases,
                app.langs,
                app.copy_of or app._id,  # If it's not a copy, must be current
                app.version,
            )
            schemas.append(repeat_case_schema)

        return cls._merge_schemas(*schemas)

    @classmethod
    def _generate_schema_from_repeat_subcases(cls, xform, repeats_with_subcases, langs, app_id, app_version):
        """
        This generates a FormExportDataSchema for repeat groups that generate subcases.

        :param xform: An XForm instance
        :param repeats_with_subcases: A list of OpenSubCaseAction classes that have a
            repeat_context.
        :param langs: An array of application languages
        :param app_id: The app_id of the corresponding app
        :param app_version: The build number of the app
        :returns: An instance of a FormExportDataSchema
        """

        repeats = cls._get_repeat_paths(xform, langs)
        schema = cls()

        def _add_to_group_schema(group_schema, path, label):
            group_schema.items.append(ExportItem(
                path=_question_path_to_path_nodes(path, repeats),
                label=label,
                last_occurrences={app_id: app_version},
            ))

        for subcase_action in repeats_with_subcases:
            group_schema = ExportGroupSchema(
                path=_question_path_to_path_nodes(subcase_action.repeat_context, repeats),
                last_occurrences={app_id: app_version},
            )
            # Add case attributes
            for case_attribute in CASE_ATTRIBUTES:
                path = u'{}/case/{}'.format(subcase_action.repeat_context, case_attribute)
                _add_to_group_schema(group_schema, path, u'case.{}'.format(case_attribute))

            # Add case updates
            for case_property, case_path in subcase_action.case_properties.iteritems():
                # This removes the repeat part of the path. For example, if inside
                # a repeat group that has the following path:
                #
                # /data/repeat/other_group/question
                #
                # We want to create a path that looks like:
                #
                # /data/repeat/case/update/other_group/question
                path_suffix = case_path[len(subcase_action.repeat_context):]
                path = u'{}/case/update{}'.format(subcase_action.repeat_context, path_suffix)
                _add_to_group_schema(group_schema, path, u'case.update.{}'.format(case_property))

            # Add case create properties
            for case_create_element in CASE_CREATE_ELEMENTS:
                path = u'{}/case/create/{}'.format(subcase_action.repeat_context, case_create_element)
                _add_to_group_schema(group_schema, path, u'case.create.{}'.format(case_create_element))

            schema.group_schemas.append(group_schema)
        return schema

    @staticmethod
    def _get_repeat_paths(xform, langs):
        return [
            question['value']
            for question in xform.get_questions(langs, include_groups=True) if question['tag'] == 'repeat'
        ]

    @classmethod
    def _generate_schema_from_xform(cls, xform, case_updates, langs, app_id, app_version):
        questions = xform.get_questions(langs, include_triggers=True)
        repeats = cls._get_repeat_paths(xform, langs)
        schema = cls()
        question_keyfn = lambda q: q['repeat']

        question_groups = [(x, list(y)) for x, y in groupby(
            sorted(questions, key=question_keyfn), question_keyfn
        )]
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
                    group_schema.items.append(item)

            if group_path is None:
                for case_update_field in case_updates:
                    group_schema.items.append(
                        ExportItem(
                            path=[
                                PathNode(name='form'),
                                PathNode(name='case'),
                                PathNode(name='update'),
                                PathNode(name=case_update_field)
                            ],
                            label="case.update.{}".format(case_update_field),
                            tag=PROPERTY_TAG_CASE,
                            last_occurrences={app_id: app_version},
                        )
                    )

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
    def _get_inferred_schema(cls, domain, case_type):
        return get_inferred_schema(domain, case_type)

    @classmethod
    def _get_current_app_ids_for_domain(cls, domain):
        return get_app_ids_in_domain(domain)

    @staticmethod
    def _get_app_build_ids_to_process(domain, app_id, last_app_versions):
        app_build_verions = get_all_built_app_ids_and_versions(domain)
        # Filter by current app id
        app_build_verions = filter(
            lambda app_build_version:
                last_app_versions.get(app_build_version.app_id, -1) < app_build_version.version,
            app_build_verions
        )
        # Map to all build ids
        return map(lambda app_build_version: app_build_version.build_id, app_build_verions)

    @staticmethod
    def get_latest_export_schema(domain, app_id, case_type):
        return get_latest_case_export_schema(domain, case_type)

    @classmethod
    def _process_app_build(cls, current_schema, app, case_type):
        case_property_mapping = get_case_properties(
            app,
            [case_type],
            include_parent_properties=False
        )
        parent_types, _ = (
            ParentCasePropertyBuilder(app)
            .get_parent_types_and_contributed_properties(case_type)
        )
        case_schemas = []
        case_schemas.append(cls._generate_schema_from_case_property_mapping(
            case_property_mapping,
            parent_types,
            app.copy_of or app._id,  # If not copy, must be current app
            app.version,
        ))
        if any(map(lambda relationship_tuple: relationship_tuple[1] == 'parent', parent_types)):
            case_schemas.append(cls._generate_schema_for_parent_case(
                app.copy_of or app._id,
                app.version,
            ))

        case_schemas.append(cls._generate_schema_for_case_history(
            case_property_mapping,
            app.copy_of or app._id,
            app.version,
        ))
        case_schemas.append(current_schema)

        return cls._merge_schemas(*case_schemas)

    @classmethod
    def _generate_schema_from_case_property_mapping(cls, case_property_mapping, parent_types, app_id, app_version):
        """
        Generates the schema for the main Case tab on the export page
        Includes system export properties for the case.
        """
        assert len(case_property_mapping.keys()) == 1
        schema = cls()

        group_schema = ExportGroupSchema(
            path=MAIN_TABLE,
            last_occurrences={app_id: app_version},
        )

        for case_type, case_properties in case_property_mapping.iteritems():

            for prop in case_properties:
                group_schema.items.append(ScalarItem(
                    path=[PathNode(name=prop)],
                    label=prop,
                    last_occurrences={app_id: app_version},
                ))

        for case_type, identifier in parent_types:
            group_schema.items.append(CaseIndexItem(
                path=[PathNode(name='indices'), PathNode(name=case_type)],
                label='{}.{}'.format(identifier, case_type),
                last_occurrences={app_id: app_version},
                tag=PROPERTY_TAG_CASE,
            ))

        schema.group_schemas.append(group_schema)
        return schema

    @classmethod
    def _generate_schema_for_parent_case(cls, app_id, app_version):
        schema = cls()
        schema.group_schemas.append(ExportGroupSchema(
            path=PARENT_CASE_TABLE,
            last_occurrences={app_id: app_version},
        ))
        return schema

    @classmethod
    def _generate_schema_for_case_history(cls, case_property_mapping, app_id, app_version):
        """Generates the schema for the Case History tab on the export page"""
        assert len(case_property_mapping.keys()) == 1
        schema = cls()

        group_schema = ExportGroupSchema(
            path=CASE_HISTORY_TABLE,
            last_occurrences={app_id: app_version},
        )
        unknown_case_properties = set(case_property_mapping[case_property_mapping.keys()[0]])

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
    merged.extend(two_keys.values())
    return merged


def _merge_dicts(one, two, resolvefn):
    """Merges two dicts. The algorithm is to first create a dictionary of all the keys that exist in one and
    two but not in both. Then iterate over each key that belongs in both while calling the resovlefn function
    to ensure the propery value gets set.

    :param one: The first dictionary
    :param two: The second dictionary
    :param resolvefn: A function that takes two values and resolves to one
    :returns: The merged dictionary
    """
    # keys either in one or two, but not both
    merged = {
        key: one.get(key, two.get(key))
        for key in one.viewkeys() ^ two.viewkeys()
    }

    # merge keys that exist in both
    merged.update({
        key: resolvefn(one[key], two[key])
        for key in one.viewkeys() & two.viewkeys()
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

        if not isinstance(value, basestring):
            return [None] * len(self.user_defined_options) + [value]

        selected = OrderedDict((x, 1) for x in value.split(" "))
        row = []
        for option in self.user_defined_options:
            row.append(selected.pop(option, None))
        row.append(" ".join(selected.keys()))
        return row

    def get_headers(self, **kwargs):
        if self.split_type == PLAIN_USER_DEFINED_SPLIT_TYPE:
            return super(SplitUserDefinedExportColumn, self).get_headers()
        header = self.label
        header_template = header if '{option}' in header else u"{name} | {option}"
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

        if not value or value == MISSING_VALUE:
            return value

        download_url = u'{url}?attachment={attachment}'.format(
            url=absolute_reverse('download_attachment', args=(domain, doc_id)),
            attachment=value,
        )
        if transform_dates:
            download_url = u'=HYPERLINK("{}")'.format(download_url)

        return download_url


class SplitGPSExportColumn(ExportColumn):
    item = SchemaProperty(GeopointItem)

    def get_headers(self, split_column=False):
        if not split_column:
            return super(SplitGPSExportColumn, self).get_headers()
        header = self.label
        header_templates = [
            _(u'{}: latitude (meters)'),
            _(u'{}: longitude (meters)'),
            _(u'{}: altitude (meters)'),
            _(u'{}: accuracy (meters)'),
        ]
        return map(lambda header_template: header_template.format(header), header_templates)

    def get_value(self, domain, doc_id, doc, base_path, split_column=False, **kwargs):
        value = super(SplitGPSExportColumn, self).get_value(
            domain,
            doc_id,
            doc,
            base_path,
            **kwargs
        )
        if not split_column:
            return value

        if value == MISSING_VALUE:
            return [MISSING_VALUE] * 4

        values = [EMPTY_VALUE] * 4

        if not isinstance(value, basestring):
            return values

        for index, coordinate in enumerate(value.split(' ')):
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

        if not isinstance(value, basestring):
            unspecified_options = [] if self.ignore_unspecified_options else [value]
            return [EMPTY_VALUE] * len(self.item.options) + unspecified_options

        selected = OrderedDict((x, 1) for x in value.split(" "))
        row = []
        for option in self.item.options:
            row.append(selected.pop(option.value, EMPTY_VALUE))
        if not self.ignore_unspecified_options:
            row.append(" ".join(selected.keys()))
        return row

    def get_headers(self, split_column=False):
        if not split_column:
            return super(SplitExportColumn, self).get_headers()
        header = self.label
        header_template = header if '{option}' in header else u"{name} | {option}"
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
            [".".join([unicode(i) for i in row_index])]
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
        case_ids = map(
            lambda index: index.get('referenced_id'),
            filter(lambda index: index.get('referenced_type') == case_type, indices)
        )
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
            is_stock_question_element = any(map(
                lambda tag_name: path_name.startswith('{}:'.format(tag_name)),
                STOCK_QUESTION_TAG_NAMES
            ))
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
                new_doc = filter(
                    lambda node: node.get('@type') == question_id,
                    value,
                )[0]
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
        combos = get_ledger_section_entry_combinations(self.domain)
        section_and_product_ids = sorted(set(map(lambda combo: (combo.entry_id, combo.section_id), combos)))
        return section_and_product_ids

    def _get_product_name(self, product_id):
        return Product.get(product_id).name

    def get_headers(self, **kwargs):
        for product_id, section in self._column_tuples:
            yield u"{product} ({section})".format(
                product=self._get_product_name(product_id),
                section=section
            )

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


class ConversionMeta(DocumentSchema):
    path = StringProperty()
    failure_reason = StringProperty()
    info = ListProperty()

    def pretty_print(self):
        print '---' * 15
        print '{:<20}| {}'.format('Original Path', self.path)
        print '{:<20}| {}'.format('Failure Reason', self.failure_reason)
        for idx, line in enumerate(self.info):
            prefix = 'Info' if idx == 0 else ''
            print '{:<20}| {}'.format(prefix, line)


class ExportMigrationMeta(Document):
    saved_export_id = StringProperty()
    domain = StringProperty()
    export_type = StringProperty(choices=[FORM_EXPORT, CASE_EXPORT])

    # The schema of the new export
    generated_schema_id = StringProperty()

    skipped_tables = SchemaListProperty(ConversionMeta)
    skipped_columns = SchemaListProperty(ConversionMeta)

    converted_tables = SchemaListProperty(ConversionMeta)
    converted_columns = SchemaListProperty(ConversionMeta)

    is_remote_app_migration = BooleanProperty(default=False)

    migration_date = DateTimeProperty()

    class Meta:
        app_label = 'export'

    @property
    def old_export_url(self):
        from corehq.apps.export.views import EditCustomCaseExportView, EditCustomFormExportView
        if self.export_type == FORM_EXPORT:
            view_cls = EditCustomFormExportView
        else:
            view_cls = EditCustomCaseExportView

        return '{}{}'.format(get_url_base(), reverse(
            view_cls.urlname,
            args=[self.domain, self.saved_export_id],
        ))


# These must match the constants in corehq/apps/export/static/export/js/const.js
MAIN_TABLE = []
CASE_HISTORY_TABLE = [PathNode(name='actions', is_repeat=True)]
PARENT_CASE_TABLE = [PathNode(name='indices', is_repeat=True)]
