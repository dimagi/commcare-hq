import os

from django.test import SimpleTestCase, TestCase
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.models import XForm, Application
from corehq.apps.export.models import ExportDataSchema


class TestExportDataSchema(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def test_basic_xform_parsing(self):
        form_xml = self.get_xml('basic_form')

        schema = ExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)

        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 2)
        self.assertEqual(group_schema.items[0].path, ['data', 'question1'])
        self.assertEqual(group_schema.items[1].path, ['data', 'question2'])

    def test_xform_parsing_with_repeat_group(self):
        form_xml = self.get_xml('repeat_group_form')

        schema = ExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            1
        )

        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.path, None)
        self.assertEqual(group_schema.items[0].path, ['data', 'question1'])

        group_schema = schema.group_schemas[1]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.path, ['data', 'question3'])
        self.assertEqual(group_schema.items[0].path, ['data', 'question3', 'question4'])

    def test_xform_parsing_with_multiple_choice(self):
        form_xml = self.get_xml('multiple_choice_form')
        schema = ExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 2)
        self.assertEqual(group_schema.items[0].path, ['data', 'question1'])

        self.assertEqual(group_schema.items[1].path, ['data', 'question2'])
        self.assertEqual(group_schema.items[1].options[0].value, 'choice1')
        self.assertEqual(group_schema.items[1].options[1].value, 'choice2')


class TestMergingExportDataSchema(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def _get_merged_schema(self, form_name1, form_name2):
        form_xml = self.get_xml(form_name1)
        form_xml2 = self.get_xml(form_name2)
        schema = ExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            1
        )
        schema2 = ExportDataSchema._generate_schema_from_xform(
            XForm(form_xml2),
            ['en'],
            2
        )

        return ExportDataSchema._merge_schema(schema, schema2)

    def test_simple_merge(self):
        """Tests merging of a form that adds a question to the form"""
        merged = self._get_merged_schema('basic_form', 'basic_form_version2')

        self.assertEqual(len(merged.group_schemas), 1)

        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 3)
        self.assertTrue(all(map(lambda item: item.last_occurrence == 2, group_schema.items)))

    def test_merge_deleted(self):
        """Tests merging of a form that deletes a question from its form"""
        merged = self._get_merged_schema('basic_form', 'basic_form_version2_delete')

        self.assertEqual(len(merged.group_schemas), 1)

        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 2)

        v1items = filter(lambda item: item.last_occurrence == 1, group_schema.items)
        v2items = filter(lambda item: item.last_occurrence == 2, group_schema.items)

        self.assertEqual(
            len(v2items),
            1,
            'There should be 1 item that was found in the second version. There was {}'.format(len(v2items))
        )
        self.assertEqual(
            len(v1items),
            1,
            'There should be 1 item that was found in the first version. There was {}'.format(len(v1items))
        )

    def test_multiple_choice_merge(self):
        """Tests merging of a form that changes the options to a multiple choice question"""
        merged = self._get_merged_schema('multiple_choice_form', 'multiple_choice_form_version2')

        self.assertEqual(len(merged.group_schemas), 1)

        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 2)

        v2items = filter(lambda item: item.last_occurrence == 2, group_schema.items)
        self.assertEqual(
            len(v2items),
            2,
        )

        multichoice = filter(lambda item: item.path == ['data', 'question2'], group_schema.items)[0]
        self.assertEqual(len(multichoice.options), 3)
        self.assertEqual(
            len(filter(lambda o: o.last_occurrence == 2, multichoice.options)),
            2,
        )

        self.assertEqual(
            len(filter(lambda o: o.last_occurrence == 1, multichoice.options)),
            1,
        )

    def test_merge_repeat_group_changed_id(self):
        """This tests merging forms that change a question to a repeat group"""
        merged = self._get_merged_schema('repeat_group_form', 'repeat_group_form_version2')

        self.assertEqual(len(merged.group_schemas), 2)
        group_schema1 = merged.group_schemas[0]
        group_schema2 = merged.group_schemas[1]

        self.assertEqual(group_schema1.last_occurrence, 2)
        self.assertEqual(len(group_schema1.items), 2)

        self.assertEqual(group_schema2.last_occurrence, 1)
        self.assertEqual(len(group_schema2.items), 1)


class TestBuildingSchemaFromApplication(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('basic_application'))

        cls.first_build = Application.wrap(cls.get_json('basic_application'))
        cls.first_build._id = '123'
        cls.first_build.copy_of = cls.current_app.get_id
        cls.first_build.version = 3

        cls.apps = [
            cls.current_app,
            cls.first_build,
        ]
        for app in cls.apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()
        # to circumvent domain.delete()'s recursive deletion that this test doesn't need

    def test_basic_application_schema(self):
        app = self.current_app

        schema = ExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            'b68a311749a6f45bdfda015b895d607012c91613'
        )

        self.assertEqual(len(schema.group_schemas), 1)
