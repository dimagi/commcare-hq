from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib
from couchdbkit.exceptions import ResourceNotFound
from dimagi.ext.couchdbkit import (
    Document, DocumentSchema, ListProperty, StringProperty,
    IntegerProperty, SetProperty, SchemaDictProperty
)
from corehq.apps.app_manager.exceptions import AppManagerException
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import is_remote_app
from corehq.apps.app_manager.dbaccessors import get_build_ids_after_version
from dimagi.utils.couch.database import iter_docs
import six
from six.moves import map


class QuestionMeta(DocumentSchema):
    options = ListProperty()
    repeat_context = StringProperty()

    class Meta(object):
        app_label = 'export'


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
    processed_apps = SetProperty(six.text_type)
    apps_with_errors = SetProperty(six.text_type)
    question_schema = SchemaDictProperty(QuestionMeta)

    class Meta(object):
        app_label = 'export'

    @classmethod
    def _get_id(cls, domain, app_id, xmlns):
        def _none_to_empty_string(str):
            return str if str is not None else ''

        key = list(map(_none_to_empty_string, [domain, app_id, xmlns]))
        return hashlib.sha1(':'.join(key).encode('utf-8')).hexdigest()

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
        all_app_ids = get_build_ids_after_version(
            self.domain,
            self.app_id,
            self.last_processed_version
        )

        all_seen_apps = self.apps_with_errors | self.processed_apps
        to_process = [app_id for app_id in all_app_ids if app_id not in all_seen_apps]
        if self.app_id not in all_seen_apps:
            to_process.append(self.app_id)

        for app_doc in iter_docs(Application.get_db(), to_process):
            if is_remote_app(app_doc):
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
        xform = app.get_xform_by_xmlns(self.xmlns, log_missing=False)
        if xform:
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
