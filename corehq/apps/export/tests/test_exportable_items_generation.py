import os

from django.test import SimpleTestCase
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.models import XForm
from corehq.apps.export.models import ExportableItems
from corehq.apps.export.const import FORM_TABLE

class TestExportableItemsFromXForm(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def setUp(self):
        pass

    def test_basic_xform_parsing(self):
        form_xml = self.get_xml('basic_form')

        items = ExportableItems._generate_conf_from_xform(
            XForm(form_xml),
            ['en'],
        )

        self.assertEqual(len(items.tables), 1)

        table = items.tables[0]

        self.assertEqual(len(table.items), 2)
        self.assertEqual(table.items[0].path, '/data/question1')
        self.assertEqual(table.items[1].path, '/data/question2')

    def test_xform_parsing_with_group(self):
        form_xml = self.get_xml('group_form')

        items = ExportableItems._generate_conf_from_xform(
            XForm(form_xml),
            ['en'],
        )

        self.assertEqual(len(items.tables), 2)

        table = items.tables[0]
        self.assertEqual(len(table.items), 1)
        self.assertEqual(table.name, FORM_TABLE)
        self.assertEqual(table.items[0].path, '/data/question2')

        table = items.tables[1]
        self.assertEqual(len(table.items), 1)
        self.assertEqual(table.name, '/data/question3')
        self.assertEqual(table.items[0].path, '/data/question3/question1')
