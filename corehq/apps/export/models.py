from couchdbkit.ext.django.schema import (
    Document, DocumentSchema, ListProperty, StringProperty,
    IntegerProperty, SetProperty, SchemaDictProperty
)

from corehq.apps.app_manager.models import Application

from dimagi.utils.couch.database import iter_docs


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
    domain = StringProperty()
    app_id = StringProperty()
    last_processed_version = IntegerProperty(default=0)
    xmlns = StringProperty()
    processed_apps = SetProperty(unicode)
    question_schema = SchemaDictProperty(QuestionMeta)

    def update_schema(self):
        if self.app_id not in self.processed_apps:
            self.update_for_app(Application.get(self.app_id))

        key = [self.domain, self.app_id]
        all_apps = Application.get_db().view(
            'app_manager/saved_app',
            startkey=key + [self.last_processed_version],
            endkey=key + [{}],
            reduce=False,
            include_docs=False,
            skip=(1 if self.last_processed_version else 0)
        ).all()

        to_process = [app['id'] for app in all_apps if app['id'] not in self.processed_apps]
        for app_doc in iter_docs(Application.get_db(), to_process):
            app = Application.wrap(app_doc)
            self.update_for_app(app)

        if to_process:
            self.save()

    def update_for_app(self, app):
        def to_json_path(xml_path):
            if not xml_path:
                return

            if xml_path.startswith('/data/'):
                xml_path = xml_path[len('/data/'):]
            return 'form.{}'.format(xml_path.replace('/', '.'))

        for question in app.get_questions(self.xmlns):
            if question['tag'] == 'select':
                question_path = to_json_path(question['value'])
                meta = self.question_schema.get(question_path, QuestionMeta(
                    repeat_context=to_json_path(question['repeat'])
                ))
                for opt in question['options']:
                    if opt['value'] not in meta.options:
                        meta.options.append(opt['value'])

                self.question_schema[question_path] = meta

        self.processed_apps.add(app.get_id)
        self.last_processed_version = app.version
