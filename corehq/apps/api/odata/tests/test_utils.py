from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase

from corehq.apps.api.odata.utils import get_odata_property_from_export_item
from corehq.apps.export.models import ExportItem


class TestOdataFromExportItem(SimpleTestCase):

    def test_get_odata_property_from_export_item(self):
        self.assertEqual(
            get_odata_property_from_export_item(ExportItem(label='form.group1.question1')),
            'form_group1_question1'
        )

    def test_get_odata_property_from_export_item_with_hashtag(self):
        self.assertEqual(
            get_odata_property_from_export_item(ExportItem(label='form.group1.#question1')),
            'form_group1_question1'
        )

    def test_get_odata_property_from_export_item_at_sign(self):
        self.assertEqual(
            get_odata_property_from_export_item(ExportItem(label='form.group1.@question1')),
            'form_group1_question1'
        )
