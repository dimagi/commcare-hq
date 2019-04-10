# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase

from corehq.apps.export.models import ExportInstance
from corehq.apps.export.models.new import DAILY_SAVED_EXPORT_ATTACHMENT_NAME


class DailySavedExportSavingTest(TestCase):

    def test_file_save_and_load(self):
        payload = b'something small and simple'
        export = ExportInstance(daily_saved_export=True, domain="test")
        export.save()
        export.set_payload(payload)
        self.assertEqual(payload, export.get_payload())

    def test_save_basic_export_to_blobdb(self):
        export = ExportInstance(daily_saved_export=True, domain="test")
        export.save()
        export.set_payload("content")
        self.assertTrue(export.has_file())
        self.assertIn(DAILY_SAVED_EXPORT_ATTACHMENT_NAME, export.external_blobs)
        self.assertEqual(export.file_size, 7)
        with export.get_payload(stream=True) as fh:
            self.assertEqual(fh.read(), b"content")
