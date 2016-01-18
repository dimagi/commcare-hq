import hashlib
from couchdbkit import SchemaListProperty, SchemaProperty
from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.userreports.expressions.getters import NestedDictGetter
from dimagi.ext.couchdbkit import (
    Document, DocumentSchema, ListProperty, StringProperty,
    IntegerProperty, SetProperty, SchemaDictProperty
)
from corehq.apps.app_manager.exceptions import AppManagerException
from corehq.apps.app_manager.models import Application
from dimagi.utils.couch.database import iter_docs

from corehq.apps.userreports import models
from dimagi.utils.decorators.memoized import memoized


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


class SplitExportColumn(ExportColumn):
    pass


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
        # Note that sub_documents will be [document] if self.repeat_path is []
        sub_documents = self._get_sub_documents(self.repeat_path, [document])
        rows = []
        for sub_doc in sub_documents:
            row = ExportRow(data=[
                col.get_value(sub_doc, self.repeat_path) for col in self.columns
            ])
            rows.append(row)
        return rows

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




class QuestionMeta(DocumentSchema):
    options = ListProperty()
    repeat_context = StringProperty()


class FormQuestionSchema(Document):
    """
    Contains information about the questions for a specific form
    specifically the options that are available (or have ever been available) for
    any multi-select questions.

    Calling `update_schema` will load the app and any saved versions of the app
    that have not already been processed and update the question schema with
    any new options.
    """
    domain = StringProperty(required=True)
    app_id = StringProperty(required=True)
    xmlns = StringProperty(required=True)

    last_processed_version = IntegerProperty(default=0)
    processed_apps = SetProperty(unicode)
    apps_with_errors = SetProperty(unicode)
    question_schema = SchemaDictProperty(QuestionMeta)

    @classmethod
    def _get_id(cls, domain, app_id, xmlns):
        def _none_to_empty_string(str):
            return str if str is not None else ''

        key = map(_none_to_empty_string, [domain, app_id, xmlns])
        return hashlib.sha1(':'.join(key)).hexdigest()

    @classmethod
    def get_by_key(cls, domain, app_id, xmlns):
        _id = cls._get_id(domain, app_id, xmlns)
        return cls.get(_id)

    @classmethod
    def get_or_create(cls, domain, app_id, xmlns):
        try:
            schema = cls.get_by_key(domain, app_id, xmlns)
        except ResourceNotFound:
            old_schemas = FormQuestionSchema.view(
                'form_question_schema/by_xmlns',
                key=[domain, app_id, xmlns],
                include_docs=True
            ).all()

            if old_schemas:
                doc = old_schemas[0].to_json()
                del doc['_id']
                del doc['_rev']
                schema = FormQuestionSchema.wrap(doc)
                schema.save()

                for old in old_schemas:
                    old.delete()
            else:
                schema = FormQuestionSchema(domain=domain, app_id=app_id, xmlns=xmlns)
                schema.save()

        return schema

    def validate(self, required=True):
        # this isn't always set, so set to empty strings if not found
        if self.app_id is None:
            self.app_id = ''

        super(FormQuestionSchema, self).validate(required=required)
        if not self.get_id:
            self._id = self._get_id(self.domain, self.app_id, self.xmlns)

    def update_schema(self):
        key = [self.domain, self.app_id]
        all_apps = Application.get_db().view(
            'app_manager/saved_app',
            startkey=key + [self.last_processed_version],
            endkey=key + [{}],
            reduce=False,
            include_docs=False,
            skip=(1 if self.last_processed_version else 0)
        ).all()

        all_seen_apps = self.apps_with_errors | self.processed_apps
        to_process = [app['id'] for app in all_apps if app['id'] not in all_seen_apps]
        if self.app_id not in all_seen_apps:
            to_process.append(self.app_id)

        for app_doc in iter_docs(Application.get_db(), to_process):
            if app_doc['doc_type'] == 'RemoteApp':
                continue
            app = Application.wrap(app_doc)
            try:
                self.update_for_app(app)
            except AppManagerException:
                self.apps_with_errors.add(app.get_id)
                self.last_processed_version = app.version

        if to_process:
            self.save()

    def update_for_app(self, app):
        form = app.get_form_by_xmlns(self.xmlns, log_missing=False)
        if form:
            xform = form.wrapped_xform()
            prefix = '/{}/'.format(xform.data_node.tag_name)

            def to_json_path(xml_path):
                if not xml_path:
                    return

                if xml_path.startswith(prefix):
                    xml_path = xml_path[len(prefix):]
                return 'form.{}'.format(xml_path.replace('/', '.'))

            for question in xform.get_questions(app.langs):
                question_path = to_json_path(question['value'])
                if question['tag'] == 'select':
                    meta = self.question_schema.get(question_path, QuestionMeta(
                        repeat_context=to_json_path(question['repeat'])
                    ))
                    for opt in question['options']:
                        if opt['value'] not in meta.options:
                            meta.options.append(opt['value'])

                    self.question_schema[question_path] = meta
                else:
                    # In the event that a question was previously a multi-select and not one any longer,
                    # we need to clear the question schema
                    self.question_schema.pop(question_path, None)

        self.processed_apps.add(app.get_id)
        self.last_processed_version = app.version
