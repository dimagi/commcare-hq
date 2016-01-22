import os

from django.test import SimpleTestCase
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.models import XForm
from corehq.apps.export.models import ExportDataSchema
from corehq.apps.export.const import FORM_TABLE


class TestExportDataSchema(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def setUp(self):
        pass

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
