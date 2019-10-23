import uuid

from django.test import SimpleTestCase, TestCase

from mock import Mock, patch
from six.moves import range

from casexml.apps.case.signals import case_post_save
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.feed.interface import Change, ChangeMeta
from pillowtop.pillow.interface import PillowBase
from pillowtop.processors.elastic import BulkElasticProcessor
from pillowtop.tests.utils import TEST_INDEX_INFO
from pillowtop.utils import bulk_fetch_changes_docs, get_errors_with_ids

from corehq.elastic import get_es_new
from corehq.form_processor.document_stores import ReadonlyCaseDocumentStore
from corehq.form_processor.signals import sql_case_post_save
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_form_for_test,
    use_sql_backend,
)
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup


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

    def test_get_errors_with_ids(self):
        errors = get_errors_with_ids([
            {'index': {'_id': 1, 'status': 500, 'error': 'e1'}},
            {'index': {'_id': 2, 'status': 500, 'error': 'e2'}}
        ])
        self.assertEqual([(1, 'e1'), (2, 'e2')], errors)


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

        cls.es = get_es_new()
        cls.index = TEST_INDEX_INFO.index

        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(cls.index)
            initialize_index_and_mapping(cls.es, TEST_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        ensure_index_deleted(cls.index)
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

    def test_process_changes_chunk(self):
        processor = BulkElasticProcessor(self.es, TEST_INDEX_INFO)

        changes = self._changes_from_ids(self.case_ids)

        retry, errors = processor.process_changes_chunk(changes)
        self.assertEqual([], retry)
        self.assertEqual([], errors)

        es_docs = self.es.mget(
            index=self.index, doc_type=TEST_INDEX_INFO.type, body={'ids': self.case_ids}, _source=True
        )['docs']
        ids_in_es = {
            doc['_source']['_id'] for doc in es_docs
        }
        self.assertEqual(set(self.case_ids), ids_in_es)

    def test_process_changes_chunk_with_errors(self):
        mock_response = (5, [{'index': {'_id': self.case_ids[0], 'error': 'DateParseError'}}])
        processor = BulkElasticProcessor(Mock(), TEST_INDEX_INFO)

        missing_case_ids = [uuid.uuid4().hex, uuid.uuid4().hex]
        changes = self._changes_from_ids(self.case_ids + missing_case_ids)

        with patch('pillowtop.processors.elastic.bulk', return_value=mock_response):
            retry, errors = processor.process_changes_chunk(changes)
        self.assertEqual(
            set(missing_case_ids),
            set([change.id for change in retry])
        )
        self.assertEqual(
            [self.case_ids[0]],
            [error[0].id for error in errors]
        )
