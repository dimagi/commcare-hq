import os
from datetime import datetime, timedelta
from django.test import TestCase
from couchforms.signals import xform_archived, xform_unarchived

from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.test_utils import FormProcessorTestUtils
from corehq.util.test_utils import TestFileMixin


class TestFormArchiving(TestCase, TestFileMixin):
    file_path = ('data', 'sample_xforms')
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        cls.interface = FormProcessorInterface('test-domain')

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()

    def testArchive(self):
        xml_data = self.get_xml('basic')
        response, xform, cases = self.interface.submit_form_locally(
            xml_data,
            'test-domain',
        )

        self.assertEqual("XFormInstance", xform.doc_type)
        self.assertEqual(0, len(xform.history))

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        xform.archive(user='mr. librarian')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)

        xform = self.interface.xform_model.get(xform.form_id)
        self.assertEqual('XFormArchived', xform.doc_type)

        [archival] = xform.history
        self.assertTrue(lower_bound <= archival.date <= upper_bound)
        self.assertEqual('archive', archival.operation)
        self.assertEqual('mr. librarian', archival.user)

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        xform.unarchive(user='mr. researcher')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)

        xform = self.interface.xform_model.get(xform.form_id)
        self.assertEqual('XFormInstance', xform.doc_type)

        [archival, restoration] = xform.history
        self.assertTrue(lower_bound <= restoration.date <= upper_bound)
        self.assertEqual('unarchive', restoration.operation)
        self.assertEqual('mr. researcher', restoration.user)

    def testSignal(self):
        global archive_counter, restore_counter
        archive_counter = 0
        restore_counter = 0

        def count_archive(**kwargs):
            global archive_counter
            archive_counter += 1

        def count_unarchive(**kwargs):
            global restore_counter
            restore_counter += 1

        xform_archived.connect(count_archive)
        xform_unarchived.connect(count_unarchive)

        xml_data = self.get_xml('basic')
        response, xform, cases = self.interface.submit_form_locally(
            xml_data,
            'test-domain',
        )

        self.assertEqual(0, archive_counter)
        self.assertEqual(0, restore_counter)

        xform.archive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(0, restore_counter)

        xform.unarchive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(1, restore_counter)
