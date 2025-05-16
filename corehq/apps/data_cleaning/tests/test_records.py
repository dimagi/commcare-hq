import uuid

from corehq.apps.data_cleaning.models import (
    BulkEditChange,
    BulkEditRecord,
    EditActionType,
)
from corehq.apps.data_cleaning.tests.test_session import BaseBulkEditSessionTest


class BulkEditRecordSelectionTest(BaseBulkEditSessionTest):
    domain_name = 'session-test-case-columns'

    @staticmethod
    def _get_case_id():
        return str(uuid.uuid4())

    def _add_change_to_record(self, record):
        change = BulkEditChange.objects.create(
            session=self.session,
            prop_id='name',
            action_type=EditActionType.STRIP,
        )
        change.records.add(record)
        return change

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

    def test_select_record_with_changes(self):
        case_id = self._get_case_id()
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_id,
            is_selected=False,
        )
        change = self._add_change_to_record(record)

        record = self.session.select_record(case_id)
        self.assertEqual(record.session, self.session)
        self.assertEqual(record.doc_id, case_id)
        self.assertTrue(record.is_selected)
        self.assertEqual(record.changes.count(), 1)
        self.assertEqual(record.changes.first(), change)

        self.assertTrue(self.session.records.filter(doc_id=case_id).exists())

    def test_deselect_record_with_changes(self):
        case_id = self._get_case_id()
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_id,
            is_selected=True,
        )
        change = self._add_change_to_record(record)

        record = self.session.deselect_record(case_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.session, self.session)
        self.assertEqual(record.doc_id, case_id)
        self.assertEqual(record.changes.count(), 1)
        self.assertEqual(record.changes.first(), change)
        self.assertFalse(record.is_selected)

        self.assertTrue(self.session.records.filter(doc_id=case_id).exists())

    def test_select_multiple_records(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_multiple_records(case_ids)
        for case_id in case_ids:
            record = self.session.records.get(doc_id=case_id)
            self.assertTrue(record.is_selected)
            self.assertEqual(record.session, self.session)
            self.assertEqual(record.doc_id, case_id)
        self.assertEqual(self.session.records.count(), len(case_ids))
        self.assertEqual(self.session.get_num_selected_records(), len(case_ids))

    def test_select_multiple_records_some_existing(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_record(case_ids[3])
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_ids[5],
            is_selected=False,
        )
        self._add_change_to_record(record)
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=self._get_case_id(),
            is_selected=False,
        )
        self._add_change_to_record(record)
        self.assertEqual(self.session.records.count(), 3)
        self.assertEqual(self.session.get_num_selected_records(), 1)
        self.session.select_multiple_records(case_ids)
        self.assertEqual(self.session.records.count(), len(case_ids) + 1)
        self.assertEqual(self.session.get_num_selected_records(), len(case_ids))

    def test_deselect_multiple_records(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_record(self._get_case_id())  # record not in case_ids
        self.session.select_multiple_records(case_ids)
        self.assertEqual(self.session.get_num_selected_records(), len(case_ids) + 1)
        self.session.deselect_multiple_records(case_ids)
        self.assertEqual(self.session.records.count(), 1)
        self.assertEqual(self.session.get_num_selected_records(), 1)

    def test_deselect_multiple_records_some_edited(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_multiple_records(case_ids)
        edited_record = self.session.records.get(doc_id=case_ids[5])
        self._add_change_to_record(edited_record)
        self.assertEqual(self.session.get_num_selected_records(), len(case_ids))
        self.session.deselect_multiple_records(case_ids)
        self.assertEqual(self.session.records.count(), 1)
        self.assertEqual(self.session.get_num_selected_records(), 0)
        edited_record = self.session.records.get(doc_id=case_ids[5])
        self.assertFalse(edited_record.is_selected)

    def test_get_unrecorded_doc_ids(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_multiple_records(case_ids)
        unrecorded_case_ids = [self._get_case_id() for _ in range(5)]
        self.assertListEqual(
            self.session.records.get_unrecorded_doc_ids(self.session, case_ids),
            []
        )
        all_case_ids = case_ids + unrecorded_case_ids
        self.assertEqual(
            set(self.session.records.get_unrecorded_doc_ids(self.session, all_case_ids)),
            set(unrecorded_case_ids)
        )
