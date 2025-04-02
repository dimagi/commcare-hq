import uuid

from corehq.apps.data_cleaning.models import BulkEditRecord
from corehq.apps.data_cleaning.tests.test_session import BaseBulkEditSessionTest


class BulkEditRecordSelectionTest(BaseBulkEditSessionTest):
    domain_name = 'session-test-case-columns'

    @staticmethod
    def _get_case_id():
        return str(uuid.uuid4())

    def test_select_record(self):
        case_id = self._get_case_id()
        record = self.session.select_record(case_id)
        self.assertEqual(record.session, self.session)
        self.assertEqual(record.doc_id, case_id)
        self.assertTrue(record.is_selected)
        self.assertTrue(self.session.records.filter(doc_id=case_id).exists())

    def test_deselect_record(self):
        case_id = self._get_case_id()
        self.session.select_record(case_id)
        record = self.session.deselect_record(case_id)
        self.assertIsNone(record)
        self.assertFalse(self.session.records.filter(doc_id=case_id).exists())

    def test_is_record_selected(self):
        case_id = self._get_case_id()
        self.session.select_record(case_id)
        self.assertTrue(self.session.is_record_selected(case_id))
        self.session.deselect_record(case_id)
        self.assertFalse(self.session.is_record_selected(case_id))

    def test_select_record_with_changes(self):
        case_id = self._get_case_id()
        change_id = uuid.uuid4()
        BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_id,
            calculated_change_id=change_id,
            is_selected=False,
        )
        self.assertFalse(self.session.is_record_selected(case_id))

        record = self.session.select_record(case_id)
        self.assertEqual(record.session, self.session)
        self.assertEqual(record.doc_id, case_id)
        self.assertTrue(record.is_selected)
        self.assertEqual(record.calculated_change_id, change_id)

        self.assertTrue(self.session.is_record_selected(case_id))
        self.assertTrue(self.session.records.filter(doc_id=case_id).exists())

    def test_deselect_record_with_changes(self):
        case_id = self._get_case_id()
        change_id = uuid.uuid4()
        BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_id,
            calculated_change_id=change_id,
            is_selected=True,
        )
        self.assertTrue(self.session.is_record_selected(case_id))

        record = self.session.deselect_record(case_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.session, self.session)
        self.assertEqual(record.doc_id, case_id)
        self.assertEqual(record.calculated_change_id, change_id)
        self.assertFalse(record.is_selected)

        self.assertFalse(self.session.is_record_selected(case_id))
        self.assertTrue(self.session.records.filter(doc_id=case_id).exists())
