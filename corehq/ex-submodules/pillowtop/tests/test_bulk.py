import uuid

from django.test import SimpleTestCase, TestCase

from six.moves import range

from casexml.apps.case.signals import case_post_save
from pillowtop.feed.interface import Change, ChangeMeta
from pillowtop.pillow.interface import PillowBase
from pillowtop.utils import bulk_fetch_changes_docs

from corehq.form_processor.document_stores import ReadonlyCaseDocumentStore
from corehq.form_processor.signals import sql_case_post_save
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_form_for_test,
    use_sql_backend,
)
from corehq.util.context_managers import drop_connected_signals


class BulkTest(SimpleTestCase):
    def test_deduplicate_changes(self):
        changes = [
            Change(1, 'a'),
            Change(2, 'a'),
            Change(3, 'a'),
            Change(2, 'b'),
            Change(4, 'a'),
            Change(1, 'b'),
        ]
        deduped = PillowBase._deduplicate_changes(changes)
        self.assertEqual(
            [(change.id, change.sequence_id) for change in deduped],
            [(3, 'a'), (2, 'b'), (4, 'a'), (1, 'b')]
        )


@use_sql_backend
class TestBulkDocOperations(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.case_ids = [
            uuid.uuid4().hex for i in range(4)
        ]
        with drop_connected_signals(case_post_save), drop_connected_signals(sql_case_post_save):
            for case_id in cls.case_ids:
                create_form_for_test(cls.domain, case_id)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        super().tearDownClass()

    def _changes_from_ids(self, case_ids):
        return [
            Change(
                id=case_id,
                sequence_id=None,
                document_store=ReadonlyCaseDocumentStore('domain'),
                metadata=ChangeMeta(
                    document_id=case_id, domain='domain', data_source_type='sql', data_source_name='case-sql'
                )
            )
            for case_id in case_ids
        ]

    def test_get_docs(self):
        missing_case_ids = [uuid.uuid4().hex, uuid.uuid4().hex]
        changes = self._changes_from_ids(self.case_ids + missing_case_ids)
        bad_changes, result_docs = bulk_fetch_changes_docs(changes, 'domain')
        self.assertEqual(
            set(self.case_ids),
            set([doc['_id'] for doc in result_docs])
        )
        self.assertEqual(
            set(missing_case_ids),
            set([change.id for change in bad_changes])
        )
