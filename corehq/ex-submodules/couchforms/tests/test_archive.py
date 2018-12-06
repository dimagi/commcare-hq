from __future__ import absolute_import
from __future__ import unicode_literals
import os
from datetime import datetime, timedelta
from django.test import TestCase
from django.test.utils import override_settings

from corehq.apps.change_feed import topics
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.util.context_managers import drop_connected_signals
from couchforms.signals import xform_archived, xform_unarchived

from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.test_utils import TestFileMixin
from testapps.test_pillowtop.utils import capture_kafka_changes_context


class TestFormArchiving(TestCase, TestFileMixin):
    file_path = ('data', 'sample_xforms')
    root = os.path.dirname(__file__)

    def setUp(self):
        super(TestFormArchiving, self).setUp()
        self.casedb = CaseAccessors('test-domain')
        self.formdb = FormAccessors('test-domain')

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        super(TestFormArchiving, self).tearDown()

    def testArchive(self):
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
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
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )

        self.assertEqual(0, archive_counter)
        self.assertEqual(0, restore_counter)

        result.xform.archive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(0, restore_counter)

        xform = self.formdb.get_form(result.xform.form_id)
        xform.unarchive()
        self.assertEqual(1, archive_counter)
        self.assertEqual(1, restore_counter)


@use_sql_backend
class TestFormArchivingSQL(TestFormArchiving):

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def testPublishChanges(self):
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )

        xform = result.xform
        with capture_kafka_changes_context(topics.FORM_SQL) as change_context:
            with drop_connected_signals(xform_archived):
                xform.archive()
        self.assertEqual(1, len(change_context.changes))
        self.assertEqual(change_context.changes[0].id, xform.form_id)

        xform = self.formdb.get_form(xform.form_id)
        with capture_kafka_changes_context(topics.FORM_SQL) as change_context:
            with drop_connected_signals(xform_unarchived):
                xform.unarchive()
        self.assertEqual(1, len(change_context.changes))
        self.assertEqual(change_context.changes[0].id, xform.form_id)
