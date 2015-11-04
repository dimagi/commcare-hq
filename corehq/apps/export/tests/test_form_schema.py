import os
from couchdbkit.exceptions import ResourceConflict

from django.test.testcases import SimpleTestCase
from fakecouch import FakeCouchDb
from jsonobject.exceptions import BadValueError

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.reports.models import FormQuestionSchema


class FormQuestionSchemaTest(SimpleTestCase, TestXmlMixin):
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

    def tearDown(self):
        FormQuestionSchema.set_db(self.db)

    def test_required_props(self):
        with self.assertRaises(BadValueError):
            schema = FormQuestionSchema(app_id=self.app_id, xmlns=self.xmlns)
            schema.save()

        # with self.assertRaises(BadValueError):
        #     schema = FormQuestionSchema(domain=self.domain, xmlns=self.xmlns)
        #     schema.save()

        with self.assertRaises(BadValueError):
            schema = FormQuestionSchema(domain=self.domain, app_id=self.app_id)
            schema.save()

    def test_unique_key(self):
        self.schema.save()

        dupe_schema = FormQuestionSchema(domain=self.domain, app_id=self.app_id, xmlns=self.xmlns)
        with self.assertRaises(ResourceConflict):
            dupe_schema.save()

    def test_get_existing(self):
        self.schema.save()

        schema = FormQuestionSchema.get_or_create(self.domain, self.app_id, self.xmlns)
        self.assertIsNotNone(schema)
        self.assertEqual(schema._rev, self.schema._rev)

    def test_get_new(self):
        self.schema.save()

        schema = FormQuestionSchema.get_or_create('new_domain', self.app_id, self.xmlns)
        self.assertIsNotNone(schema)

    def test_migrate_old(self):
        self.schema._id = '123'
        self.schema.last_processed_version = 12
        self.schema.save()
        second_schema = FormQuestionSchema(domain=self.domain, app_id=self.app_id, xmlns=self.xmlns, _id='1234')
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

        schema = FormQuestionSchema.get_or_create(self.domain, self.app_id, self.xmlns)
        self.assertEqual(schema.last_processed_version, self.schema.last_processed_version)
        self.assertNotEqual(schema.get_id, self.schema.get_id)
        self.assertNotEqual(schema.get_id, second_schema.get_id)
        self.assertEqual(len(self.fakedb.mock_docs), 1)
        self.assertTrue(schema.get_id in self.fakedb.mock_docs)
