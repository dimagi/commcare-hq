import os
import mock
from datetime import datetime, timedelta
from django.test import TestCase
from django.test.utils import override_settings

from corehq.apps.userreports.tasks import reprocess_archive_stubs
from corehq.apps.change_feed import topics
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.util.context_managers import drop_connected_signals
from couchforms.signals import xform_archived, xform_unarchived

from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.test_utils import TestFileMixin
from couchforms.models import UnfinishedArchiveStub
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

    def testUnfinishedArchiveStub(self):
        # Test running the celery task reprocess_archive_stubs on an existing archive stub
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))

        # Mock the archive function throwing an error
        with mock.patch('couchforms.signals.xform_archived.send') as mock_send:
            try:
                mock_send.side_effect = Exception
                xform.archive(user_id='librarian')
            except Exception:
                pass

        # Get the form with the updated history, it should be archived
        xform = self.formdb.get_form(xform.form_id)
        self.assertEqual(1, len(xform.history))
        self.assertTrue(xform.is_archived)
        [archival] = xform.history
        self.assertEqual('archive', archival.operation)
        self.assertEqual('librarian', archival.user)

        # The case associated with the form should still exist, it was not rebuilt because of the exception
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)

        # There should be a stub for the unfinished archive
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 1)
        self.assertEqual(unfinished_archive_stubs[0].history_updated, True)
        self.assertEqual(unfinished_archive_stubs[0].user_id, 'librarian')
        self.assertEqual(unfinished_archive_stubs[0].domain, 'test-domain')
        self.assertEqual(unfinished_archive_stubs[0].archive, True)

        # Manually call the periodic celery task that reruns archiving/unarchiving actions
        reprocess_archive_stubs()

        # The case and stub should both be deleted now
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)
        unfinished_archive_stubs_after_reprocessing = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs_after_reprocessing), 0)

    def testUnfinishedUnarchiveStub(self):
        # Test running the celery task reprocess_archive_stubs on an existing unarchive stub
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))

        # Archive the form successfully
        xform.archive(user_id='librarian')

        # Mock the unarchive function throwing an error
        with mock.patch('couchforms.signals.xform_unarchived.send') as mock_send:
            try:
                mock_send.side_effect = Exception
                xform.unarchive(user_id='librarian')
            except Exception:
                pass

        # Make sure the history only has an archive and an unarchive
        xform = self.formdb.get_form(xform.form_id)
        self.assertEqual(2, len(xform.history))
        self.assertFalse(xform.is_archived)
        self.assertEqual('archive', xform.history[0].operation)
        self.assertEqual('librarian', xform.history[0].user)
        self.assertEqual('unarchive', xform.history[1].operation)
        self.assertEqual('librarian', xform.history[1].user)

        # The case should not exist because the unarchived form was not rebuilt
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)

        # There should be a stub for the unfinished unarchive
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 1)
        self.assertEqual(unfinished_archive_stubs[0].history_updated, True)
        self.assertEqual(unfinished_archive_stubs[0].user_id, 'librarian')
        self.assertEqual(unfinished_archive_stubs[0].domain, 'test-domain')
        self.assertEqual(unfinished_archive_stubs[0].archive, False)

        # Manually call the periodic celery task that reruns archiving/unarchiving actions
        reprocess_archive_stubs()

        # The case should be back, and the stub should be deleted now
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)
        unfinished_archive_stubs_after_reprocessing = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs_after_reprocessing), 0)

    def testUnarchivingWithArchiveStub(self):
        # Test a user-initiated unarchive with an existing archive stub
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))
        # Mock the archive function throwing an error
        with mock.patch('couchforms.signals.xform_archived.send') as mock_send:
            try:
                mock_send.side_effect = Exception
                xform.archive(user_id='librarian')
            except Exception:
                pass

        # There should be a stub for the unfinished archive
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 1)
        self.assertEqual(unfinished_archive_stubs[0].history_updated, True)
        self.assertEqual(unfinished_archive_stubs[0].user_id, 'librarian')
        self.assertEqual(unfinished_archive_stubs[0].domain, 'test-domain')
        self.assertEqual(unfinished_archive_stubs[0].archive, True)

        # Call an unarchive
        xform.unarchive(user_id='librarian')

        # The unfinished archive stub should be deleted
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 0)

        # The case should exist because the case close was unarchived
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)

        # Manually call the periodic celery task that reruns archiving/unarchiving actions
        reprocess_archive_stubs()

        # Make sure the case still exists (to double check that the archive stub was deleted)
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)

    def testArchivingWithUnarchiveStub(self):
        # Test a user-initiated archive with an existing unarchive stub
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))

        # Archive the form successfully
        xform.archive(user_id='librarian')

        # Mock the unarchive function throwing an error
        with mock.patch('couchforms.signals.xform_unarchived.send') as mock_send:
            try:
                mock_send.side_effect = Exception
                xform.unarchive(user_id='librarian')
            except Exception:
                pass

        # There should be a stub for the unfinished unarchive
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 1)
        self.assertEqual(unfinished_archive_stubs[0].history_updated, True)
        self.assertEqual(unfinished_archive_stubs[0].user_id, 'librarian')
        self.assertEqual(unfinished_archive_stubs[0].domain, 'test-domain')
        self.assertEqual(unfinished_archive_stubs[0].archive, False)

        # Call an archive
        xform.archive(user_id='librarian')

        # The unfinished archive stub should be deleted
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 0)

        # The case should not exist because the case close was archived
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)

        # Manually call the periodic celery task that reruns archiving/unarchiving actions
        reprocess_archive_stubs()

        # The history should not have been added to, make sure that it still only has one entry

        # Make sure the case still does not exist (to double check that the unarchive stub was deleted)
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)

    def testUnfinishedArchiveStubErrorAddingHistory(self):
        # Test running the celery task reprocess_archive_stubs on an existing archive stub where the archive
        # initially failed on updating the history
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))

        # Mock the couch and sql archive function throwing an error (so that this test works for both)
        tmp = 'corehq.form_processor.backends.%s.dbaccessors.%s'
        with mock.patch(tmp % ('sql', 'FormAccessorSQL.set_archived_state')) as mock_operation_sql:
            with mock.patch(tmp % ('couch', 'XFormOperation')) as mock_operation_couch:
                try:
                    mock_operation_sql.side_effect = Exception
                    mock_operation_couch.side_effect = Exception
                    xform.archive(user_id='librarian')
                except Exception:
                    pass

        # Get the form with the updated history, make sure it has not been archived yet
        xform = self.formdb.get_form(xform.form_id)
        self.assertEqual(0, len(xform.history))
        self.assertFalse(xform.is_archived)

        # The case associated with the form should still exist, it was not rebuilt because of the exception
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)

        # There should be a stub for the unfinished archive, and the history should not be updated yet
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 1)
        self.assertEqual(unfinished_archive_stubs[0].history_updated, False)
        self.assertEqual(unfinished_archive_stubs[0].user_id, 'librarian')
        self.assertEqual(unfinished_archive_stubs[0].domain, 'test-domain')
        self.assertEqual(unfinished_archive_stubs[0].archive, True)

        # Manually call the periodic celery task that reruns archiving/unarchiving actions
        reprocess_archive_stubs()

        # Make sure the history shows an archive now
        xform = self.formdb.get_form(xform.form_id)
        self.assertEqual(1, len(xform.history))
        self.assertTrue(xform.is_archived)
        [archival] = xform.history
        self.assertEqual('archive', archival.operation)
        self.assertEqual('librarian', archival.user)

        # The case and stub should both be deleted now
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)
        unfinished_archive_stubs_after_reprocessing = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs_after_reprocessing), 0)

    def testUnfinishedUnarchiveStubErrorAddingHistory(self):
        # Test running the celery task reprocess_archive_stubs on an existing archive stub where the archive
        # initially failed on updating the history
        case_id = 'ddb8e2b3-7ce0-43e4-ad45-d7a2eebe9169'
        xml_data = self.get_xml('basic')
        result = submit_form_locally(
            xml_data,
            'test-domain',
        )
        xform = result.xform
        self.assertTrue(xform.is_normal)
        self.assertEqual(0, len(xform.history))

        # Archive the form successfully
        xform.archive(user_id='librarian')

        # Mock the couch and sql archive function throwing an error (so that this test works for both)
        tmp = 'corehq.form_processor.backends.%s.dbaccessors.%s'
        with mock.patch(tmp % ('sql', 'FormAccessorSQL.set_archived_state')) as mock_operation_sql:
            with mock.patch(tmp % ('couch', 'XFormOperation')) as mock_operation_couch:
                try:
                    mock_operation_sql.side_effect = Exception
                    mock_operation_couch.side_effect = Exception
                    xform.unarchive(user_id='librarian')
                except Exception:
                    pass

        # Get the form with the updated history, make sure it only has one entry (the archive)
        xform = self.formdb.get_form(xform.form_id)
        self.assertEqual(1, len(xform.history))
        self.assertTrue(xform.is_archived)
        [archival] = xform.history
        self.assertEqual('archive', archival.operation)
        self.assertEqual('librarian', archival.user)

        # The case associated with the form should not exist, it was not rebuilt because of the exception
        case = self.casedb.get_case(case_id)
        self.assertTrue(case.is_deleted)

        # There should be a stub for the unfinished archive, and the history should not be updated yet
        unfinished_archive_stubs = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs), 1)
        self.assertEqual(unfinished_archive_stubs[0].history_updated, False)
        self.assertEqual(unfinished_archive_stubs[0].user_id, 'librarian')
        self.assertEqual(unfinished_archive_stubs[0].domain, 'test-domain')
        self.assertEqual(unfinished_archive_stubs[0].archive, False)

        # Manually call the periodic celery task that reruns archiving/unarchiving actions
        reprocess_archive_stubs()

        # Make sure the history shows an archive and an unarchive now
        xform = self.formdb.get_form(xform.form_id)
        self.assertEqual(2, len(xform.history))
        self.assertFalse(xform.is_archived)
        self.assertEqual('archive', xform.history[0].operation)
        self.assertEqual('librarian', xform.history[0].user)
        self.assertEqual('unarchive', xform.history[1].operation)
        self.assertEqual('librarian', xform.history[1].user)

        # The case should be back, and the stub should be deleted now
        case = self.casedb.get_case(case_id)
        self.assertFalse(case.is_deleted)
        unfinished_archive_stubs_after_reprocessing = UnfinishedArchiveStub.objects.filter()
        self.assertEqual(len(unfinished_archive_stubs_after_reprocessing), 0)

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
