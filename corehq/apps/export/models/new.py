from datetime import datetime
from itertools import groupby
from collections import defaultdict, OrderedDict, namedtuple

from couchdbkit.ext.django.schema import IntegerProperty
from django.utils.translation import ugettext as _
from couchdbkit import SchemaListProperty, SchemaProperty, BooleanProperty, DictProperty

from corehq.apps.userreports.expressions.getters import NestedDictGetter
from corehq.apps.app_manager.dbaccessors import (
    get_built_app_ids_for_app_id,
    get_all_built_app_ids_and_versions,
    get_latest_built_app_ids_and_versions,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import get_case_properties
from corehq.apps.reports.display import xmlns_to_name
from corehq.blobs.mixin import BlobMixin
from couchexport.models import Format
from couchexport.transforms import couch_to_excel_datetime
from dimagi.utils.couch.database import iter_docs
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    ListProperty,
    StringProperty,
    DateTimeProperty,
)
from corehq.apps.export.utils import (
    is_valid_transform
)
from corehq.apps.export.const import (
    PROPERTY_TAG_UPDATE,
    PROPERTY_TAG_DELETED,
    FORM_EXPORT,
    CASE_EXPORT,
    TRANSFORM_FUNCTIONS,
    DEID_TRANSFORM_FUNCTIONS,
    PROPERTY_TAG_ROW,
    PROPERTY_TAG_CASE,
)
from corehq.apps.export.dbaccessors import (
    get_latest_case_export_schema,
    get_latest_form_export_schema,
)


DAILY_SAVED_EXPORT_ATTACHMENT_NAME = "payload"


class PathNode(DocumentSchema):

    name = StringProperty(required=True)
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

    @classmethod
    def wrap(cls, data):
        if cls is ExportItem:
            doc_type = data['doc_type']
            if doc_type == 'ExportItem':
                return super(ExportItem, cls).wrap(data)
            elif doc_type == 'ScalarItem':
                return ScalarItem.wrap(data)
            elif doc_type == 'MultipleChoiceItem':
                return MultipleChoiceItem.wrap(data)
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
        item = cls(one.to_json())
        item.last_occurrences = _merge_dicts(one.last_occurrences, two.last_occurrences, max)
        return item

    @property
    def readable_path(self):
        return '.'.join(map(lambda node: node.name, self.path))


class ExportColumn(DocumentSchema):
    item = SchemaProperty(ExportItem)
    label = StringProperty()
    # Determines whether or not to show the column in the UI Config without clicking advanced
    is_advanced = BooleanProperty(default=False)
    selected = BooleanProperty(default=False)
    tags = ListProperty()

    # A list of constants that map to functions to transform the column value
    transforms = ListProperty(validators=is_valid_transform)

    def get_value(self, doc, base_path, transform_dates=False, row_index=None):
        """
        Get the value of self.item of the given doc.
        When base_path is [], doc is a form submission or case,
        when base_path is non empty, doc is a repeat group from a form submission.
        :param doc: A form submission or instance of a repeat group in a submission or case
        :param base_path:
        :return:
        """
        # Confirm the ExportItem's path starts with the base_path
        assert base_path == self.item.path[:len(base_path)]
        # Get the path from the doc root to the desired ExportItem
        path = [x.name for x in self.item.path[len(base_path):]]
        return self._transform(NestedDictGetter(path)(doc), transform_dates)

    def _transform(self, value, transform_dates):
        """
        Transform the given value with the transforms specified in self.transforms.
        Also transform dates if the transform_dates flag is true.
        """
        # TODO: The functions in self.transforms might expect docs, not values, in which case this needs to move.

        if transform_dates:
            value = couch_to_excel_datetime(value, None)
        for transform in self.transforms:
            value = TRANSFORM_FUNCTIONS[transform](value, None)
        return value

    @staticmethod
    def create_default_from_export_item(table_path, item, app_ids_and_versions):
        """Creates a default ExportColumn given an item

        :param table_path: The path of the table_path that the item belongs to
        :param item: An ExportItem instance
        :param app_ids_and_versions: A dictionary of app ids that map to latest build version
        :returns: An ExportColumn instance
        """
        is_case_update = item.tag == PROPERTY_TAG_CASE

        is_main_table = table_path == MAIN_TABLE
        constructor_args = {
            "item": item,
            "label": item.label,
            "is_advanced": is_case_update or False,
            "transforms": [],
        }

        if item.tag == PROPERTY_TAG_ROW:
            column_class = RowNumberColumn
            constructor_args["repeat"] = len([node for node in table_path if node.is_repeat])
        else:
            column_class = ExportColumn

        column = column_class(**constructor_args)
        column.update_properties_from_app_ids_and_versions(app_ids_and_versions)
        column.selected = not column._is_deleted(app_ids_and_versions) and is_main_table and not is_case_update
        return column

    def _is_deleted(self, app_ids_and_versions):
        is_deleted = True
        for app_id, version in app_ids_and_versions.iteritems():
            if self.item.last_occurrences.get(app_id) == version:
                is_deleted = False
                break
        return is_deleted

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
        return bool(set(self.transforms) & set(DEID_TRANSFORM_FUNCTIONS))

    def get_headers(self):
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
    # label saves the user's decision for the table name
    label = StringProperty()
    path = ListProperty(PathNode)
    columns = ListProperty(ExportColumn)
    selected = BooleanProperty(default=False)

    def __hash__(self):
        return hash(tuple(self.path))

    @property
    def selected_columns(self):
        """The columns that should be included in the export"""
        return [c for c in self.columns if c.selected]

    def get_headers(self):
        """
        Return a list of column headers
        """
        headers = []
        for column in self.selected_columns:
            headers.extend(column.get_headers())
        return headers

    def get_rows(self, document, row_number):
        """
        Return a list of ExportRows generated for the given document.
        :param document: dictionary representation of a form submission or case
        :param row_number: number indicating this documents index in the sequence of all documents in the export
        :return: List of ExportRows
        """
        sub_documents = self._get_sub_documents(document, row_number)
        rows = []
        for doc_row in sub_documents:
            doc, row_index = doc_row.doc, doc_row.row

            row_data = []
            for col in self.selected_columns:
                val = col.get_value(doc, self.path, row_index=row_index)
                if isinstance(val, list):
                    row_data.extend(val)
                else:
                    row_data.append(val)
            rows.append(ExportRow(data=row_data))
        return rows

    def get_column(self, item_path, column_transforms):
        # Columns should be unique by item path and column.transforms minus any deid transforms
        filtered_column_transforms = [
            t for t in column_transforms if t not in DEID_TRANSFORM_FUNCTIONS.keys()
        ]
        for column in self.columns:
            transforms = [t for t in column.transforms if t not in DEID_TRANSFORM_FUNCTIONS.keys()]
            if column.item.path == item_path and transforms == filtered_column_transforms:
                return column
        return None

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
            else:
                new_docs.append(DocRow(row=row_index, doc=next_doc))
        return TableConfiguration._get_sub_documents_helper(path[1:], new_docs)


class ExportInstance(BlobMixin, Document):
    name = StringProperty()
    type = StringProperty()
    domain = StringProperty()
    tables = ListProperty(TableConfiguration)
    export_format = StringProperty(default='csv')

    # Whether to split multiselects into multiple columns
    split_multiselects = BooleanProperty(default=False)

    # Whether to automatically convert dates to excel dates
    transform_dates = BooleanProperty(default=False)

    # Whether to include duplicates and other error'd forms in export
    include_errors = BooleanProperty(default=False)

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
        """For compatability with old exports"""
        return self.is_deidentified

    @property
    def defaults(self):
        return FormExportInstanceDefaults if self.type == FORM_EXPORT else CaseExportInstanceDefaults

    def get_table(self, path):
        for table in self.tables:
            if table.path == path:
                return table
        return None

    @classmethod
    def _new_from_schema(cls, schema):
        raise NotImplementedError()

    @classmethod
    def generate_instance_from_schema(cls, schema, saved_export=None):
        """Given an ExportDataSchema, this will generate an ExportInstance"""
        if saved_export:
            instance = saved_export
        else:
            instance = cls._new_from_schema(schema)

        instance.name = instance.name or instance.defaults.get_default_instance_name(schema)

        latest_app_ids_and_versions = get_latest_built_app_ids_and_versions(
            schema.domain,
            getattr(schema, 'app_id', None),
        )
        for group_schema in schema.group_schemas:
            table = instance.get_table(group_schema.path) or TableConfiguration(
                path=group_schema.path,
                label=instance.defaults.get_default_table_name(group_schema.path),
                selected=instance.defaults.default_is_table_selected(group_schema.path),
            )
            columns = []
            for item in group_schema.items:
                column = table.get_column(
                    item.path, []
                ) or ExportColumn.create_default_from_export_item(
                    table.path,
                    item,
                    latest_app_ids_and_versions,
                )

                # Ensure that the item is up to date
                column.item = item

                # Need to rebuild tags and other flags based on new build ids
                column.update_properties_from_app_ids_and_versions(latest_app_ids_and_versions)
                columns.append(column)

            cls._insert_system_properties(schema.type, table, columns)
            table.columns = columns

            if not instance.get_table(group_schema.path):
                instance.tables.append(table)

        return instance

    @classmethod
    def _insert_system_properties(cls, export_type, table, columns):
        if export_type == FORM_EXPORT:
            if table.path == MAIN_TABLE:
                cls._insert_form_system_properties(table, columns)
            else:
                cls._insert_form_repeat_system_properties(table, columns)
        elif export_type == CASE_EXPORT:
            if table.path == MAIN_TABLE:
                cls._insert_case_system_properties(table, columns)
            elif table.path == CASE_HISTORY_TABLE:
                cls._insert_case_history_system_properties(table, columns)
            elif table.path == PARENT_CASE_TABLE:
                cls._insert_parent_case_table(table, columns)

    @classmethod
    def _insert_form_repeat_system_properties(cls, table, columns):
        from corehq.apps.export.system_properties import ROW_NUMBER_COLUMN
        existing_column = table.get_column(
            ROW_NUMBER_COLUMN.item.path, ROW_NUMBER_COLUMN.transforms

        )
        columns.insert(0, existing_column or ROW_NUMBER_COLUMN)

    @classmethod
    def _insert_parent_case_table(cls, table, columns):
        from corehq.apps.export.system_properties import PARENT_CASE_TABLE_PROPERTIES

        for static_column in PARENT_CASE_TABLE_PROPERTIES:
            existing_column = table.get_column(static_column.item.path, static_column.transforms)
            columns.insert(0, existing_column or static_column)

    @classmethod
    def _insert_case_history_system_properties(cls, table, columns):
        from corehq.apps.export.system_properties import CASE_HISTORY_PROPERTIES

        # insert columns for system properties
        for static_column in reversed(CASE_HISTORY_PROPERTIES):
            existing_column = table.get_column(
                static_column.item.path,
                static_column.transforms
            )
            columns.insert(0, existing_column or static_column)

    @classmethod
    def _insert_case_system_properties(cls, table, columns):
        from corehq.apps.export.system_properties import (
            TOP_MAIN_CASE_TABLE_PROPERTIES,
            BOTTOM_MAIN_CASE_TABLE_PROPERTIES
        )

        # insert columns for system properties
        for static_column in reversed(TOP_MAIN_CASE_TABLE_PROPERTIES):
            existing_column = table.get_column(
                static_column.item.path,
                static_column.transforms
            )
            columns.insert(0, existing_column or static_column)

        for static_column in BOTTOM_MAIN_CASE_TABLE_PROPERTIES:
            existing_column = table.get_column(
                static_column.item.path,
                static_column.transforms
            )
            columns.append(existing_column or static_column)

    @classmethod
    def _insert_form_system_properties(cls, table, columns):
        from corehq.apps.export.system_properties import TOP_MAIN_FORM_TABLE_PROPERTIES, BOTTOM_MAIN_FORM_TABLE_PROPERTIES

        first_case_update_index = len(columns)
        for i, col in enumerate(columns):
            if col.tags == [PROPERTY_TAG_CASE]:
                first_case_update_index = i
                break

        # insert columns for system properties
        for insertion_index, static_props in [
            (first_case_update_index, BOTTOM_MAIN_FORM_TABLE_PROPERTIES),
            (0, TOP_MAIN_FORM_TABLE_PROPERTIES),

        ]:
            for static_column in reversed(static_props):
                existing_column = table.get_column(
                    static_column.item.path,
                    static_column.transforms
                )
                columns.insert(insertion_index, existing_column or static_column)

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

    @classmethod
    def _new_from_schema(cls, schema):
        return cls(
            type=schema.type,
            domain=schema.domain,
            case_type=schema.case_type,
        )


class FormExportInstance(ExportInstance):
    xmlns = StringProperty()
    app_id = StringProperty()

    # Whether to include duplicates and other error'd forms in export
    include_errors = BooleanProperty(default=False)

    @property
    def formname(self):
        return xmlns_to_name(self.domain, self.xmlns, self.app_id)

    @classmethod
    def _new_from_schema(cls, schema):
        return cls(
            type=schema.type,
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
        return u'{}: {}'.format(
            xmlns_to_name(schema.domain, schema.xmlns, schema.app_id),
            datetime.now().strftime('%Y-%m-%d')
        )

    @staticmethod
    def get_default_table_name(table_path):
        if table_path == MAIN_TABLE:
            return _('Forms')
        else:
            return _('Repeat: {}').format((table_path[-1].name if len(table_path) else None) or "")


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
            copyfn=lambda option: Option(option.to_json())
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


class ExportDataSchema(Document):
    """
    An object representing the things that can be exported for a particular
    form xmlns or case type. It contains a list of ExportGroupSchema.
    """
    domain = StringProperty()
    created_on = DateTimeProperty(default=datetime.utcnow)
    group_schemas = SchemaListProperty(ExportGroupSchema)

    # A map of app_id to app_version. Represents the last time it saw an app and at what version
    last_app_versions = DictProperty()
    datatype_mapping = defaultdict(lambda: ScalarItem, {
        'MSelect': MultipleChoiceItem,
    })

    class Meta:
        app_label = 'export'

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
                return'{}:{}'.format(
                    _path_nodes_to_string(export_item.path),
                    export_item.doc_type,
                )

            group_schema = ExportGroupSchema(
                path=group_schema1.path,
                last_occurrences=_merge_dicts(
                    group_schema1.last_occurrences,
                    group_schema2.last_occurrences,
                    max
                )
            )
            items = _merge_lists(
                group_schema1.items,
                group_schema2.items,
                keyfn=keyfn,
                resolvefn=lambda item1, item2: item1.__class__.merge(item1, item2),
                copyfn=lambda item: item.__class__(item.to_json()),
            )
            group_schema.items = items
            return group_schema

        previous_group_schemas = schemas[0].group_schemas
        for current_schema in schemas[1:]:
            group_schemas = _merge_lists(
                previous_group_schemas,
                current_schema.group_schemas,
                keyfn=lambda group_schema: _path_nodes_to_string(group_schema.path),
                resolvefn=resolvefn,
                copyfn=lambda group_schema: ExportGroupSchema(group_schema.to_json())
            )
            previous_group_schemas = group_schemas

        schema.group_schemas = group_schemas

        return schema

    def record_update(self, app_id, app_version):
        self.last_app_versions[app_id] = max(
            self.last_app_versions.get(app_id, 0),
            app_version,
        )

class FormExportDataSchema(ExportDataSchema):

    app_id = StringProperty()
    xmlns = StringProperty()

    @property
    def type(self):
        return FORM_EXPORT

    @staticmethod
    def generate_schema_from_builds(domain, app_id, form_xmlns, force_rebuild=False):
        """Builds a schema from Application builds for a given identifier

        :param domain: The domain that the export belongs to
        :param app_id: The app_id that the export belongs to
        :param unique_form_id: The unique identifier of the item being exported
        :returns: Returns a FormExportDataSchema instance
        """
        original_id, original_rev = None, None
        current_xform_schema = get_latest_form_export_schema(domain, app_id, form_xmlns)
        if current_xform_schema and not force_rebuild:
            original_id, original_rev = current_xform_schema._id, current_xform_schema._rev
        else:
            current_xform_schema = FormExportDataSchema()

        app_build_ids = get_built_app_ids_for_app_id(
            domain,
            app_id,
            current_xform_schema.last_app_versions.get(app_id)
        )

        for app_doc in iter_docs(Application.get_db(), app_build_ids):
            app = Application.wrap(app_doc)
            xform = app.get_form_by_xmlns(form_xmlns, log_missing=False)
            if not xform:
                continue
            case_updates = xform.get_case_updates(xform.get_module().case_type)
            xform = xform.wrapped_xform()
            xform_schema = FormExportDataSchema._generate_schema_from_xform(
                xform,
                case_updates,
                app.langs,
                app.copy_of,
                app.version,
            )
            current_xform_schema = FormExportDataSchema._merge_schemas(current_xform_schema, xform_schema)
            current_xform_schema.record_update(app.copy_of, app.version)

        if original_id and original_rev:
            current_xform_schema._id = original_id
            current_xform_schema._rev = original_rev
        current_xform_schema.domain = domain
        current_xform_schema.app_id = app_id
        current_xform_schema.xmlns = form_xmlns
        current_xform_schema.save()

        return current_xform_schema

    @staticmethod
    def _generate_schema_from_xform(xform, case_updates, langs, app_id, app_version):
        questions = xform.get_questions(langs)
        repeats = [r['value'] for r in xform.get_questions(langs, include_groups=True) if r['tag'] == 'repeat']
        schema = FormExportDataSchema()
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
                item = FormExportDataSchema.datatype_mapping[question['type']].create_from_question(
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


class CaseExportDataSchema(ExportDataSchema):

    case_type = StringProperty()

    @property
    def type(self):
        return CASE_EXPORT

    @staticmethod
    def _get_app_build_ids_to_process(domain, last_app_versions):
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
    def generate_schema_from_builds(domain, case_type, force_rebuild=False):
        """Builds a schema from Application builds for a given identifier

        :param domain: The domain that the export belongs to
        :param unique_form_id: The unique identifier of the item being exported
        :returns: Returns a CaseExportDataSchema instance
        """

        original_id, original_rev = None, None
        current_case_schema = get_latest_case_export_schema(domain, case_type)

        if current_case_schema and not force_rebuild:
            # Save the original id an rev so we can later save the document under the same _id
            original_id, original_rev = current_case_schema._id, current_case_schema._rev
        else:
            current_case_schema = CaseExportDataSchema()

        app_build_ids = CaseExportDataSchema._get_app_build_ids_to_process(
            domain,
            current_case_schema.last_app_versions,
        )

        for app_doc in iter_docs(Application.get_db(), app_build_ids):
            app = Application.wrap(app_doc)
            case_property_mapping = get_case_properties(
                app,
                [case_type],
                include_parent_properties=False
            )
            case_schema = CaseExportDataSchema._generate_schema_from_case_property_mapping(
                case_property_mapping,
                app.copy_of,
                app.version,
            )
            case_history_schema = CaseExportDataSchema._generate_schema_for_case_history(
                case_property_mapping,
                app.copy_of,
                app.version,
            )
            case_parent_schema = CaseExportDataSchema._generate_schema_for_parent_case(
                app.copy_of,
                app.version,
            )

            current_case_schema = CaseExportDataSchema._merge_schemas(
                case_schema,
                case_history_schema,
                case_parent_schema,
                current_case_schema,
            )

            current_case_schema.record_update(app.copy_of, app.version)

        if original_id and original_rev:
            current_case_schema._id = original_id
            current_case_schema._rev = original_rev
        current_case_schema.domain = domain
        current_case_schema.case_type = case_type
        current_case_schema.save()

        return current_case_schema

    @staticmethod
    def _generate_schema_from_case_property_mapping(case_property_mapping, app_id, app_version):
        """
        Generates the schema for the main Case tab on the export page
        Includes system export properties for the case.
        """
        assert len(case_property_mapping.keys()) == 1
        schema = CaseExportDataSchema()

        for case_type, case_properties in case_property_mapping.iteritems():
            group_schema = ExportGroupSchema(
                path=MAIN_TABLE,
                last_occurrences={app_id: app_version},
            )

            for prop in case_properties:
                group_schema.items.append(ScalarItem(
                    path=[PathNode(name=prop)],
                    label=prop,
                    last_occurrences={app_id: app_version},
                ))

            schema.group_schemas.append(group_schema)

        return schema

    @staticmethod
    def _generate_schema_for_parent_case(app_id, app_version):
        schema = CaseExportDataSchema()
        schema.group_schemas.append(ExportGroupSchema(
            path=PARENT_CASE_TABLE,
            last_occurrences={app_id: app_version},
        ))
        return schema

    @staticmethod
    def _generate_schema_for_case_history(case_property_mapping, app_id, app_version):
        """Generates the schema for the Case History tab on the export page"""
        assert len(case_property_mapping.keys()) == 1
        schema = CaseExportDataSchema()

        group_schema = ExportGroupSchema(
            path=CASE_HISTORY_TABLE,
            last_occurrences={app_id: app_version},
        )

        for case_type, case_properties in case_property_mapping.iteritems():
            for prop in case_properties:
                # Yeah... let's not hard code this list everywhere
                # This list comes from casexml.apps.case.xml.parser.CaseActionBase.from_v2
                if prop in ["type", "name", "external_id", "user_id", "owner_id", "opened_on"]:
                    path_start = PathNode(name="updated_known_properties")
                else:
                    path_start = PathNode(name="updated_unknown_properties")

                group_schema.items.append(ScalarItem(
                    path=CASE_HISTORY_TABLE + [path_start, PathNode(name=prop)],
                    label=prop,
                    tag=PROPERTY_TAG_UPDATE,
                    last_occurrences={app_id: app_version},
                ))

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
    assert parts[0] == ""
    parts = parts[1:]

    repeat_test_string = ""
    path = []
    for part in parts:
        repeat_test_string += "/" + part
        path.append(PathNode(name=part, is_repeat=repeat_test_string in repeats))

    assert path[0] == PathNode(name="data")
    path[0].name = "form"
    return path


def _path_nodes_to_string(path, separator=' '):
    if not path or (len(path) == 1 and path[0] is None):
        return ''
    return separator.join(["{}.{}".format(node.name, node.is_repeat) for node in path])


def _merge_lists(one, two, keyfn, resolvefn, copyfn):
    """Merges two lists. The algorithm is to first iterate over the first list. If the item in the first list
    does not exist in the second list, add that item to the merged list. If the item does exist in the second
    list, resolve the conflict using the resolvefn. After the first list has been iterated over, simply append
    any items in the second list that have not already been added.

    :param one: The first list to be merged.
    :param two: The second list to be merged.
    :param keyfn: A function that takes an element from the list as an argument and returns a unique
        identifier for that item.
    :param resolvefn: A function that takes two elements that resolve to the same key and returns a single
        element that has resolved the conflict between the two elements.
    :param copyfn: A function that takes an element as its argument and returns a copy of it.
    :returns: A list of the merged elements
    """

    merged = []
    two_keys = set(map(lambda obj: keyfn(obj), two))

    for obj in one:

        if keyfn(obj) in two_keys:
            # If obj exists in both list, must merge
            two_keys.remove(keyfn(obj))
            new_obj = resolvefn(
                obj,
                filter(lambda other: keyfn(other) == keyfn(obj), two)[0],
            )
        else:
            new_obj = copyfn(obj)

        merged.append(new_obj)

    # Filter any objects we've already added by merging
    filtered = filter(lambda obj: keyfn(obj) in two_keys, two)
    merged.extend(
        # Map objects to new object
        map(lambda obj: copyfn(obj), filtered)
    )
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
    """
    item = SchemaProperty(MultipleChoiceItem)
    ignore_unspecified_options = BooleanProperty()

    def get_value(self, doc, base_path, row_index=None):
        """
        Get the value of self.item of the given doc.
        When base_path is [], doc is a form submission or case,
        when base_path is non empty, doc is a repeat group from a form submission.
        doc is a form submission or instance of a repeat group in a submission or case
        """
        value = super(SplitExportColumn, self).get_value(doc, base_path)
        if not isinstance(value, basestring):
            return [None] * len(self.item.options) + [] if self.ignore_unspecified_options else [value]

        selected = OrderedDict((x, 1) for x in value.split(" "))
        row = []
        for option in self.item.options:
            row.append(selected.pop(option.value, None))
        if not self.ignore_unspecified_options:
            row.append(" ".join(selected.keys()))
        return row

    def get_headers(self):
        header_template = self.label if '{option}' in self.label else u"{name} | {option}"
        headers = []
        for option in self.item.options:
            headers.append(
                header_template.format(
                    name=self.label,
                    option=option.value
                )
            )
        if not self.ignore_unspecified_options:
            headers.append(
                header_template.format(
                    name=self.label,
                    option='extra'
                )
            )
        return headers


class RowNumberColumn(ExportColumn):
    repeat = IntegerProperty(default=0)

    def get_headers(self):
        headers = [self.label]
        if self.repeat > 0:
            headers += ["{}__{}".format(self.label, i) for i in range(self.repeat + 1)]
        return headers

    def get_value(self, doc, base_path, transform_dates=False, row_index=None):
        assert row_index
        return (
            [".".join([unicode(i) for i in row_index])]
            + (list(row_index) if len(row_index) > 1 else [])
        )


# These must match the constants in corehq/apps/export/static/export/js/const.js
MAIN_TABLE = []
CASE_HISTORY_TABLE = [PathNode(name='actions', is_repeat=True)]
PARENT_CASE_TABLE = [PathNode(name='indices', is_repeat=True)]
