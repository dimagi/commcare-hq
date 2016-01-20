from couchdbkit import SchemaListProperty, SchemaProperty

from corehq.apps.userreports.expressions.getters import NestedDictGetter
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
    path = SchemaListProperty(StringProperty)
    label = StringProperty()
    last_occurrence = IntegerProperty()


class ExportColumn(DocumentSchema):
    item = SchemaProperty(ExportItem)
    display = StringProperty()

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

    table_name = StringProperty()
    repeat_path = ListProperty(StringProperty)
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

class ExportRow(object):
    def __init__(self, data):
        self.data = data


class RepeatGroup(DocumentSchema):
    path = SchemaListProperty(StringProperty)
    last_occurrence = IntegerProperty()
    items = SchemaListProperty(ExportItem)


class ExportableItems(DocumentSchema):
    """
    An object representing the things that can be exported for a particular
    form xmlns or case type.
    Each item in the list is uniquely identified by its path and doc_type.
    repeats is a list of RepeatGroups, present at any level of the question hierarchy
    """
    items = SchemaListProperty(ExportItem)
    repeats = SchemaListProperty(RepeatGroup)


class ScalarItem(ExportItem):
    """
    A text, numeric, date, etc. question or case property
    """
    data_type = StringProperty()


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
    choices = SchemaListProperty(Option)
