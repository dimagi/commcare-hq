from datetime import datetime
from itertools import groupby
from collections import defaultdict, OrderedDict
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
    CASE_HISTORY_PROPERTIES,
    CASE_HISTORY_TABLE,
    MAIN_TABLE_PROPERTIES,
    FORM_EXPORT,
    CASE_EXPORT,
    MAIN_TABLE,
    TRANSFORM_FUNCTIONS,
    DEID_TRANSFORM_FUNCTIONS)
from corehq.apps.export.dbaccessors import (
    get_latest_case_export_schema,
    get_latest_form_export_schema,
)


class ExportItem(DocumentSchema):
    """
    An item for export.

    path: A question path like ["my_group", "q1"] or a case property name
        like ["date_of_birth"].

    label: The label of the corresponding form question, or the case property name
    tag: Denotes whether the property is a system, meta, etc
    last_occurrences: A dictionary that maps an app_id to the last version the export item was present
    """
    path = ListProperty()
    label = StringProperty()
    tag = StringProperty()
    last_occurrences = DictProperty()

    @classmethod
    def create_from_question(cls, question, app_id, app_version):
        return cls(
            path=_question_path_to_doc_path(question['value']),
            label=question['label'],
            last_occurrences={app_id: app_version},
        )

    @classmethod
    def merge(cls, one, two):
        item = cls(one.to_json())
        item.last_occurrences = _merge_dicts(one.last_occurrences, two.last_occurrences, max)
        return item


class ExportColumn(DocumentSchema):
    item = SchemaProperty(ExportItem)
    label = StringProperty()
    # Determines whether or not to show the column in the UI Config without clicking advanced
    is_advanced = BooleanProperty(default=False)
    selected = BooleanProperty(default=False)
    tags = ListProperty()

    # A list of constants that map to functions to transform the column value
    transforms = ListProperty(validators=is_valid_transform)

    def get_value(self, doc, base_path, transform_dates=False):
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
        path = self.item.path[len(base_path):]
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
            value = TRANSFORM_FUNCTIONS[transform](value)
        return value

    @staticmethod
    def create_default_from_export_item(group_schema_path, item, app_ids_and_versions):
        """Creates a default ExportColumn given an item

        :param group_schema_path: The path of the group_schema that the item belongs to
        :param item: An ExportItem instance
        :param app_ids_and_versions: A dictionary of app ids that map to latest build version
        :returns: An ExportColumn instance
        """

        is_main_table = group_schema_path == MAIN_TABLE

        column = ExportColumn(
            item=item,
            label=item.label,
        )
        column.update_properties_from_app_ids_and_versions(app_ids_and_versions)
        column.selected = not column._is_deleted(app_ids_and_versions) and is_main_table
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
        self.is_advanced = is_deleted
        self.tags = tags

    @property
    def is_deidentifed(self):
        # TODO: Might be better if we set an is_deidentified flag on the model instead?
        return bool(set(self.transforms) & set(DEID_TRANSFORM_FUNCTIONS))

    def get_headers(self):
        # TODO: id columns need special treatment
        # see couchexport.models.ExportTable#get_headers_row
        if self.is_deidentifed:
            return [u"{} {}".format(self.label, "[sensitive]")]
        else:
            return [self.label]


class TableConfiguration(DocumentSchema):
    # label saves the user's decision for the table name
    label = StringProperty()
    path = ListProperty()
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

    def get_rows(self, document):
        """
        Return a list of ExportRows generated for the given document.
        :param document: dictionary representation of a form submission or case
        :return: List of ExportRows
        """
        # Note that sub_documents will be [document] if self.path is []
        sub_documents = self._get_sub_documents(self.path, [document])
        rows = []
        for doc in sub_documents:

            row_data = []
            for col in self.selected_columns:
                val = col.get_value(doc, self.path)
                if isinstance(val, list):
                    row_data.extend(val)
                else:
                    row_data.append(val)
            rows.append(ExportRow(data=row_data))
        return rows

    def get_column(self, item_path):
        for column in self.columns:
            if column.item.path == item_path:
                return column
        return None

    def _get_sub_documents(self, path, docs):
        """
        Return each instance of a repeat group at the path from the given docs.
        If path is [], just return the docs

        >>> TableConfiguration()._get_sub_documents(['foo'], [{'foo': {'bar': 'a'}}, {'foo': {'bar': 'b'}}])
        [{'bar': 'a'}, {'bar': 'b'}]
        >>> TableConfiguration()._get_sub_documents(['foo', 'bar'], [{'foo': [{'bar': {'baz': 'a'}}, {'bar': {'baz': 'b'}},]}]
        [{'baz': 'a'}, {'baz': 'b'}]

        :param path: A list of a strings
        :param docs: A list of dicts representing form submissions
        :return:
        """
        if len(path) == 0:
            return docs

        new_docs = []
        for doc in docs:
            next_doc = doc.get(path[0], {})
            if type(next_doc) == list:
                new_docs.extend(next_doc)
            else:
                new_docs.append(next_doc)
        return self._get_sub_documents(path[1:], new_docs)


class ExportInstance(Document):
    name = StringProperty()
    type = StringProperty()
    domain = StringProperty()
    tables = ListProperty(TableConfiguration)
    export_format = StringProperty(default='csv')
    last_built = DateTimeProperty()

    # Whether to split multiselects into multiple columns
    split_multiselects = BooleanProperty(default=False)

    # Whether to automatically convert dates to excel dates
    transform_dates = BooleanProperty(default=False)

    # Whether to include duplicates and other error'd forms in export
    include_errors = BooleanProperty(default=False)

    # Whether the export is de-identified
    is_deidentified = BooleanProperty(default=False)
    is_daily_saved_export = BooleanProperty(default=False)

    # Keep reference to old schema id if we have converted it from the legacy infrastructure
    legacy_saved_export_schema_id = StringProperty()

    class Meta:
        app_label = 'export'

    @property
    def is_safe(self):
        """For compatability with old exports"""
        return self.is_deidentified

    @property
    def file_id(self):
        return 'placeholder'

    @property
    def export_size(self):
        return 'placeholder'

    @property
    def download_url(self):
        return 'placeholder'

    @property
    def defaults(self):
        return FormExportInstanceDefaults if self.type == FORM_EXPORT else CaseExportInstanceDefaults

    def get_table(self, path):
        for table in self.tables:
            if table.path == path:
                return table
        return None

    def daily_saved_export_metadata(self):
        return {
            'fileId': self.file_id,
            'size': self.export_size,
            'lastUpdated': self.last_built,
            'showExpiredWarning': False,
            'downloadUrl': self.download_url,
        }

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
                column = table.get_column(item.path) or ExportColumn.create_default_from_export_item(
                    table.path,
                    item,
                    latest_app_ids_and_versions,
                )

                # Ensure that the item is up to date
                column.item = item

                # Need to rebuild tags and other flags based on new build ids
                column.update_properties_from_app_ids_and_versions(latest_app_ids_and_versions)
                columns.append(column)
            table.columns = columns

            if not instance.get_table(group_schema.path):
                instance.tables.append(table)

        return instance


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
            return _('Repeat: {}').format(_list_path_to_string(table_path))


class CaseExportInstanceDefaults(ExportInstanceDefaults):

    @staticmethod
    def get_default_table_name(table_path):
        if table_path == MAIN_TABLE:
            return _('Cases')
        elif table_path == CASE_HISTORY_TABLE:
            return _('Case History')
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
    def create_from_question(cls, question, app_id, app_version):
        item = super(MultipleChoiceItem, cls).create_from_question(question, app_id, app_version)

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
    path = ListProperty()
    items = SchemaListProperty(ExportItem)
    last_occurrence = DictProperty()


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
                keyfn=lambda item: '{}:{}'.format(_list_path_to_string(item.path), item.doc_type),
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
                keyfn=lambda group_schema: _list_path_to_string(group_schema.path),
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
    def generate_schema_from_builds(domain, app_id, form_xmlns):
        """Builds a schema from Application builds for a given identifier

        :param domain: The domain that the export belongs to
        :param app_id: The app_id that the export belongs to
        :param unique_form_id: The unique identifier of the item being exported
        :returns: Returns a FormExportDataSchema instance
        """
        original_id, original_rev = None, None
        current_xform_schema = get_latest_form_export_schema(domain, app_id, form_xmlns)
        if current_xform_schema:
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
            xform = xform.wrapped_xform()
            xform_schema = FormExportDataSchema._generate_schema_from_xform(
                xform,
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
    def _generate_schema_from_xform(xform, langs, app_id, app_version):
        questions = xform.get_questions(langs)
        schema = FormExportDataSchema()

        for group_path, group_questions in groupby(questions, lambda q: q['repeat']):
            # If group_path is None, that means the questions are part of the form and not a repeat group
            # inside of the form
            group_schema = ExportGroupSchema(
                path=_question_path_to_doc_path(group_path),
                last_occurrences={app_id: app_version},
            )
            if group_path is None:
                for system_prop in MAIN_TABLE_PROPERTIES:
                    group_schema.items.append(ScalarItem(
                        path=[system_prop.name],
                        label=system_prop.name,
                        tag=system_prop.tag,
                        last_occurrences={app_id: app_version},
                    ))

            for question in group_questions:
                # Create ExportItem based on the question type
                item = FormExportDataSchema.datatype_mapping[question['type']].create_from_question(
                    question,
                    app_id,
                    app_version,
                )
                group_schema.items.append(item)

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
    def generate_schema_from_builds(domain, case_type):
        """Builds a schema from Application builds for a given identifier

        :param domain: The domain that the export belongs to
        :param unique_form_id: The unique identifier of the item being exported
        :returns: Returns a CaseExportDataSchema instance
        """

        original_id, original_rev = None, None
        current_case_schema = get_latest_case_export_schema(domain, case_type)

        if current_case_schema:
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

            current_case_schema = CaseExportDataSchema._merge_schemas(
                current_case_schema,
                case_schema,
                case_history_schema
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
        """Generates the schema for the main Case tab on the export page"""
        assert len(case_property_mapping.keys()) == 1
        schema = CaseExportDataSchema()

        for case_type, case_properties in case_property_mapping.iteritems():
            group_schema = ExportGroupSchema(
                path=MAIN_TABLE,
                last_occurrences={app_id: app_version},
            )
            for prop in case_properties:
                group_schema.items.append(ScalarItem(
                    path=[prop],
                    label=prop,
                    last_occurrences={app_id: app_version},
                ))

            schema.group_schemas.append(group_schema)

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
        for system_prop in CASE_HISTORY_PROPERTIES:
            group_schema.items.append(ScalarItem(
                path=[system_prop.name],
                label=system_prop.name,
                tag=system_prop.tag,
                last_occurrences={app_id: app_version},
            ))

        for case_type, case_properties in case_property_mapping.iteritems():
            for prop in case_properties:
                group_schema.items.append(ScalarItem(
                    path=[prop],
                    label=prop,
                    tag=PROPERTY_TAG_UPDATE,
                    last_occurrences={app_id: app_version},
                ))

        schema.group_schemas.append(group_schema)
        return schema


def _string_path_to_list(path):
    return path if path is None else path[1:].split('/')


def _question_path_to_doc_path(string_path):
    """
    Convert a question path into the format expected by the export code,
    specifically the logic in ExportColumn.get_value().
    The export code will use this path to traverse the JSON representation of
    the form that is stored in ElasticSearch.

    E.g. "/data/question1/" is converted to ["form", "question1"]
    """
    path = _string_path_to_list(string_path)
    if path is None:
        path = []
    else:
        assert path[0] == "data"
        path[0] = "form"
    return path


def _list_path_to_string(path, separator='.'):
    if not path or (len(path) == 1 and path[0] is None):
        return ''
    return separator.join(path)


def _merge_lists(one, two, keyfn, resolvefn, copyfn):
    """Merges two lists. The alogorithm is to first iterate over the first list. If the item in the first list
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

    def get_value(self, doc, base_path):
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


class SavedBasicExport(BlobMixin, Document):
    """
    A cache of an export that lives in couch.
    Doesn't do anything smart, just works off an index
    """
    configuration = SchemaProperty(ExportConfiguration)
    last_updated = DateTimeProperty()
    last_accessed = DateTimeProperty()

    @property
    def size(self):
        try:
            return self.blobs[self.get_attachment_name()].content_length
        except KeyError:
            return 0

    def has_file(self):
        return self.get_attachment_name() in self.blobs

    def get_attachment_name(self):
        # obfuscate this because couch doesn't like attachments that start with underscores
        return hashlib.md5(unicode(self.configuration.filename).encode('utf-8')).hexdigest()

    def set_payload(self, payload):
        self.put_attachment(payload, self.get_attachment_name())

    def get_payload(self, stream=False):
        return self.fetch_attachment(self.get_attachment_name(), stream=stream)

    @classmethod
    def by_index(cls, index):
        return SavedBasicExport.view(
            "couchexport/saved_exports",
            key=json.dumps(index),
            include_docs=True,
            reduce=False,
        ).all()
