import os
from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.signals import xform_archived, xform_unarchived

from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.util.test_utils import TestFileMixin


class TestFormArchiving(TestCase, TestFileMixin):
    file_path = ('data', 'sample_xforms')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.casedb = CaseAccessors('test-domain')
        self.formdb = FormAccessors('test-domain')

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()

    @run_with_all_backends
    def testArchive(self):
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        response, xform, cases = submit_form_locally(
            xml_data,
            'test-domain',
        )

        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        xform.archive(user_id='mr. librarian')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)

        xform = self.formdb.get_form(xform.form_id)
        self.assertTrue(xform.is_archived)
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)
        self.assertEqual(case.xform_ids, [])

        [archival] = xform.history
        self.assertTrue(lower_bound <= archival.date <= upper_bound)
        self.assertEqual('archive', archival.operation)
        self.assertEqual('mr. librarian', archival.user)

        lower_bound = datetime.utcnow() - timedelta(seconds=1)
        xform.unarchive(user_id='mr. researcher')
        upper_bound = datetime.utcnow() + timedelta(seconds=1)

        xform = self.formdb.get_form(xform.form_id)
        self.assertTrue(xform.is_normal)
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)
        self.assertEqual(case.xform_ids, [xform.form_id])

        [archival, restoration] = xform.history
        self.assertTrue(lower_bound <= restoration.date <= upper_bound)
        self.assertEqual('unarchive', restoration.operation)
        self.assertEqual('mr. researcher', restoration.user)

    @run_with_all_backends
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
        response, xform, cases = submit_form_locally(
            xml_data,
            'test-domain',
        )

        self.assertEqual(0, archive_counter)
        self.assertEqual(0, restore_counter)

        xform.archive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(0, restore_counter)

        xform = self.formdb.get_form(xform.form_id)
        xform.unarchive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(1, restore_counter)
