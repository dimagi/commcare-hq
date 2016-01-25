from itertools import groupby
from collections import defaultdict
from couchdbkit import SchemaListProperty, SchemaProperty

from corehq.apps.userreports.expressions.getters import NestedDictGetter
from corehq.apps.app_manager.dbaccessors import get_built_app_ids_for_app_id
from corehq.apps.app_manager.models import Application
from dimagi.utils.couch.database import iter_docs
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    ListProperty,
    StringProperty,
    IntegerProperty,
)


class ExportItem(DocumentSchema):
    """
    An item for export.
    path is a question path like ["my_group", "q1"] or a case property name
    like ["date_of_birth"].
    """
    path = ListProperty()
    label = StringProperty()
    last_occurrence = IntegerProperty()

    @classmethod
    def create_from_question(cls, question, appVersion):
        return cls(
            path=_string_path_to_list(question['value']),
            label=question['label'],
            last_occurrence=appVersion,
        )

    @classmethod
    def merge(cls, one, two):
        item = cls(one.to_json())
        item.last_occurrence = max(one.last_occurrence, two.last_occurrence)
        return item


class ExportColumn(DocumentSchema):
    item = SchemaProperty(ExportItem)
    label = StringProperty()

    def get_value(self, doc, base_path):
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
        return NestedDictGetter(path)(doc)


class TableConfiguration(DocumentSchema):

    name = StringProperty()
    repeat_path = StringProperty()
    columns = ListProperty(ExportColumn)

    def get_rows(self, document):
        """
        Return a list of ExportRows generated for the given document.
        :param document: dictionary representation of a form submission or case
        :return: List of ExportRows
        """
        # Note that repeat_items will be [document] if self.repeat_path is []
        repeat_items = self._get_items_for_repeat(self.repeat_path, [document])
        rows = []
        for item in repeat_items:
            row = ExportRow(data=[
                col.get_value(item, self.repeat_path) for col in self.columns
            ])
            rows.append(row)
        return rows

    def _get_items_for_repeat(self, path, docs):
        """
        Return each instance of a repeat group at the path from the given docs.
        If path is [], just return the docs

        >>> TableConfiguration()._get_items_for_repeat(['foo'], [{'foo': {'bar': 'a'}}, {'foo': {'bar': 'b'}}])
        [{'bar': 'a'}, {'bar': 'b'}]
        >>> TableConfiguration()._get_items_for_repeat(['foo', 'bar'], [{'foo': [{'bar': {'baz': 'a'}}, {'bar': {'baz': 'b'}},]}]
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
        return self._get_items_for_repeat(path[1:], new_docs)


class ExportInstance(Document):

    class Meta:
        app_label = 'export'


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

    last_occurrence is an app build number representing the last version of the app in
    which this option was present.
    """
    last_occurrence = IntegerProperty()
    value = StringProperty()


class MultipleChoiceItem(ExportItem):
    """
    A multiple choice question or case property
    Choices is the union of choices for the question in each of the builds with
    this question.
    """
    options = SchemaListProperty(Option)

    @classmethod
    def create_from_question(cls, question, appVersion):
        item = super(MultipleChoiceItem, cls).create_from_question(question, appVersion)

        for option in question['options']:
            item.options.append(Option(
                last_occurrence=appVersion,
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
                    last_occurrence=max(option1.last_occurrence, option2.last_occurrence)
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
    last_occurrence = IntegerProperty()


class ExportDataSchema(DocumentSchema):
    """
    An object representing the things that can be exported for a particular
    form xmlns or case type. It contains a list of ExportGroupSchema.
    """
    group_schemas = SchemaListProperty(ExportGroupSchema)
    datatype_mapping = defaultdict(lambda: ScalarItem, {
        'MSelect': MultipleChoiceItem,
    })

    @staticmethod
    def generate_schema_from_builds(domain, app_id, unique_form_id):
        app_build_ids = get_built_app_ids_for_app_id(domain, app_id)
        all_xform_conf = ExportDataSchema()

        for app_doc in iter_docs(Application.get_db(), app_build_ids):
            app = Application.wrap(app_doc)
            xform = app.get_form(unique_form_id).wrapped_xform()
            xform_conf = ExportDataSchema._generate_schema_from_xform(xform, app.langs, app.version)
            all_xform_conf = ExportDataSchema._merge_schema(all_xform_conf, xform_conf)

        return all_xform_conf

    @staticmethod
    def _generate_schema_from_xform(xform, langs, appVersion):
        questions = xform.get_questions(langs)
        schema = ExportDataSchema()

        for group_path, group_questions in groupby(questions, lambda q: q['repeat']):
            # If group_path is None, that means the questions are part of the form and not a repeat group
            # inside of the form
            group_schema = ExportGroupSchema(
                path=_string_path_to_list(group_path),
                last_occurrence=appVersion,
            )
            for question in group_questions:
                # Create ExportItem based on the question type
                item = ExportDataSchema.datatype_mapping[question['type']].create_from_question(
                    question,
                    appVersion,
                )
                group_schema.items.append(item)

            schema.group_schemas.append(group_schema)

        return schema

    @staticmethod
    def _merge_schema(schema1, schema2):
        """Merges two ExportDataSchemas together

        :param schema1: The first ExportDataSchema
        :param schema2: The second ExportDataSchema
        :returns: The merged ExportDataSchema
        """

        schema = ExportDataSchema()

        def resolvefn(group_schema1, group_schema2):
            group_schema = ExportGroupSchema(
                path=group_schema1.path,
                last_occurrence=max(group_schema1.last_occurrence, group_schema2.last_occurrence),
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

        group_schemas = _merge_lists(
            schema1.group_schemas,
            schema2.group_schemas,
            keyfn=lambda group_schema: _list_path_to_string(group_schema.path),
            resolvefn=resolvefn,
            copyfn=lambda group_schema: ExportGroupSchema(group_schema.to_json())
        )

        schema.group_schemas = group_schemas

        return schema


def _string_path_to_list(path):
    return path if path is None else path[1:].split('/')


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
