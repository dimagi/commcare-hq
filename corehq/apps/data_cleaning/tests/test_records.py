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
        assert record.session == self.session
        assert record.doc_id == case_id
        assert record.is_selected
        assert self.session.records.filter(doc_id=case_id).exists()

    def test_deselect_record(self):
        case_id = self._get_case_id()
        self.session.select_record(case_id)
        record = self.session.deselect_record(case_id)
        assert record is None
        assert not self.session.records.filter(doc_id=case_id).exists()

    def test_select_record_with_changes(self):
        case_id = self._get_case_id()
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_id,
            is_selected=False,
        )
        change = self._add_change_to_record(record)

        record = self.session.select_record(case_id)
        assert record.session == self.session
        assert record.doc_id == case_id
        assert record.is_selected
        assert record.changes.count() == 1
        assert record.changes.first() == change

        assert self.session.records.filter(doc_id=case_id).exists()

    def test_deselect_record_with_changes(self):
        case_id = self._get_case_id()
        record = BulkEditRecord.objects.create(
            session=self.session,
            doc_id=case_id,
            is_selected=True,
        )
        change = self._add_change_to_record(record)

        record = self.session.deselect_record(case_id)
        assert record is not None
        assert record.session == self.session
        assert record.doc_id == case_id
        assert record.changes.count() == 1
        assert record.changes.first() == change
        assert not record.is_selected

        assert self.session.records.filter(doc_id=case_id).exists()

    def test_select_multiple_records(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_multiple_records(case_ids)
        for case_id in case_ids:
            record = self.session.records.get(doc_id=case_id)
            assert record.is_selected
            assert record.session == self.session
            assert record.doc_id == case_id
        assert self.session.records.count() == len(case_ids)
        assert self.session.get_num_selected_records() == len(case_ids)

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
        assert self.session.records.count() == 3
        assert self.session.get_num_selected_records() == 1
        self.session.select_multiple_records(case_ids)
        assert self.session.records.count() == len(case_ids) + 1
        assert self.session.get_num_selected_records() == len(case_ids)

    def test_deselect_multiple_records(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_record(self._get_case_id())  # record not in case_ids
        self.session.select_multiple_records(case_ids)
        assert self.session.get_num_selected_records() == len(case_ids) + 1
        self.session.deselect_multiple_records(case_ids)
        assert self.session.records.count() == 1
        assert self.session.get_num_selected_records() == 1

    def test_deselect_multiple_records_some_edited(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_multiple_records(case_ids)
        edited_record = self.session.records.get(doc_id=case_ids[5])
        self._add_change_to_record(edited_record)
        assert self.session.get_num_selected_records() == len(case_ids)
        self.session.deselect_multiple_records(case_ids)
        assert self.session.records.count() == 1
        assert self.session.get_num_selected_records() == 0
        edited_record = self.session.records.get(doc_id=case_ids[5])
        assert not edited_record.is_selected

    def test_get_unrecorded_doc_ids(self):
        case_ids = [self._get_case_id() for _ in range(10)]
        self.session.select_multiple_records(case_ids)
        unrecorded_case_ids = [self._get_case_id() for _ in range(5)]
        assert self.session.records.get_unrecorded_doc_ids(self.session, case_ids) == []
        all_case_ids = case_ids + unrecorded_case_ids
        assert set(self.session.records.get_unrecorded_doc_ids(self.session, all_case_ids)) == set(
            unrecorded_case_ids
        )
