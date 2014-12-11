import os

from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.export.utils import get_or_create_question_schema
from corehq.apps.reports.models import FormQuestionSchema


class FormQuestionSchemaTest(SimpleTestCase, TestFileMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def test(self):
        app = Application.wrap(self.get_json('question_schema_test_app'))
        app._id = '123'
        app.version = 1

        xmlns = 'http://openrosa.org/formdesigner/284D3F7C-9C10-48E6-97AC-C37927CBA89A'
        schema = FormQuestionSchema(xmlns=xmlns)

        schema.update_for_app(app)
        self.assertIn(app.get_id, schema.processed_apps)
        self.assertEqual(app.version, schema.last_processed_version)
        self.assertEqual(schema.question_schema['form.multi_root'].options, ['item1', 'item2', 'item3'])
        self.assertEqual(schema.question_schema['form.group1.multi_level1'].options, ['item1', 'item2'])
        self.assertEqual(schema.question_schema['form.group1.question6.multi_level_2'].options, ['item1', 'item2'])
        self.assertEqual(schema.question_schema['form.repeat_1.multi_level_1_repeat'].options, ['item1', 'item2'])
        self.assertEqual(schema.question_schema['form.repeat_1.multi_level_1_repeat'].repeat_context, 'form.repeat_1')

        updated_form_xml = self.get_xml('question_schema_update_form')
        app.get_form_by_xmlns(xmlns).source = updated_form_xml
        app.version = 2

        schema.update_for_app(app)
        self.assertEqual(1, len(schema.processed_apps))
        self.assertIn(app.get_id, schema.processed_apps)
        self.assertEqual(app.version, schema.last_processed_version)
        self.assertEqual(schema.question_schema['form.new_multi'].options, ['z_first', 'a_last'])
        self.assertEqual(schema.question_schema['form.group1.multi_level1'].options, ['item1', 'item2', '1_item'])


class TestGetOrCreateSchema(SimpleTestCase):
    def setUp(self):
        self.db = FormQuestionSchema.get_db()
        self.fakedb = FakeCouchDb()
        FormQuestionSchema.set_db(self.fakedb)

        self.domain = 'test'
        self.app_id = '123'
        self.xmlns = 'this_xmlns'
        self.schema = FormQuestionSchema(domain=self.domain, app_id=self.app_id, xmlns=self.xmlns)
        self.schema.save()
        assert len(self.fakedb.mock_docs) == 1

    def tearDown(self):
        FormQuestionSchema.set_db(self.db)

    def test_get_by_id(self):
        schema = get_or_create_question_schema(self.domain, self.app_id, self.xmlns, self.schema.get_id)
        self.assertIsNotNone(schema)
        self.assertEqual(len(self.fakedb.mock_docs), 1)

    def test_get_from_view(self):
        self.fakedb.add_view(
            'form_question_schema/by_xmlns',
            [(
                {'key': [self.domain, self.app_id, self.xmlns], 'include_docs': True},
                [
                    self.schema.to_json()
                ]
            )]
        )

        schema = get_or_create_question_schema(self.domain, self.app_id, self.xmlns)
        self.assertIsNotNone(schema)
        self.assertEqual(len(self.fakedb.mock_docs), 1)

    def test_multiple_results(self):
        second_schema = FormQuestionSchema(domain=self.domain, app_id=self.app_id, xmlns=self.xmlns)
        second_schema.save()
        self.assertEqual(len(self.fakedb.mock_docs), 2)

        self.fakedb.add_view(
            'form_question_schema/by_xmlns',
            [(
                {'key': [self.domain, self.app_id, self.xmlns], 'include_docs': True},
                [
                    self.schema.to_json(), second_schema.to_json()
                ]
            )]
        )

        schema = get_or_create_question_schema(self.domain, self.app_id, self.xmlns)
        self.assertIsNotNone(schema)
        self.assertEqual(len(self.fakedb.mock_docs), 1)
