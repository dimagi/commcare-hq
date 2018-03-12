from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from mock import patch, MagicMock

from corehq.apps.export.models import FormExportInstance, CaseExportInstance
from corehq.apps.reports.tasks import saved_exports


class TestDailySavedExports(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDailySavedExports, cls).setUpClass()
        cls.exports = [
            FormExportInstance(is_daily_saved_export=True),
            FormExportInstance(is_daily_saved_export=False),
            CaseExportInstance(is_daily_saved_export=True),
        ]
        for export in cls.exports:
            export.save()

    @classmethod
    def tearDownClass(cls):
        for export in cls.exports:
            export.delete()
        super(TestDailySavedExports, cls).tearDownClass()

    def test_saved_exports_task(self):

        class MockExportFile(object):

            def __enter__(self):
                return ""

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        magic_mock = MagicMock(return_value=MockExportFile())
        with patch("corehq.apps.export.tasks.rebuild_export", new=magic_mock):
            saved_exports()
            self.assertEqual(magic_mock.call_count, 2)
