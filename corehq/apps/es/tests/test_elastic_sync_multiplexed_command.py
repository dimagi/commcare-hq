from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings
from corehq.apps.es.exceptions import IndexNotMultiplexedException

from corehq.apps.es.client import (
    create_document_adapter,
    manager,
)
from corehq.apps.es.tests.utils import (
    TestDoc,
    TestDocumentAdapter,
    es_test,
)

COMMAND_NAME = 'elastic_sync_multiplexed'
INDEX_CNAME = 'test_reindex'


def mutiplexed_adapter_with_overriden_settings():
    with override_settings(ES_FOR_TEST_INDEX_MULTIPLEXED=True):
        return create_document_adapter(
            TestDocumentAdapter,
            "test_reindex-primary",
            "test_doc",
            secondary="test_reindex-secondary",
        )


adapter_cname_map = {
    INDEX_CNAME: mutiplexed_adapter_with_overriden_settings(),
}


def mock_doc_adapter_from_cname(cname):
    return adapter_cname_map[cname]


def mock_iter_index_cnames():
    return list(adapter_cname_map)


@es_test(requires=[mutiplexed_adapter_with_overriden_settings()])
@patch(
    "corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname",
    mock_doc_adapter_from_cname,
)
@patch(
    "corehq.apps.es.management.commands.elastic_sync_multiplexed.iter_index_cnames",
    mock_iter_index_cnames,
)
class TestElasticSyncMultiplexedCommand(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.adapter = mutiplexed_adapter_with_overriden_settings()

    def test_invalid_index_canonical_raises(self):
        with self.assertRaises(CommandError):
            call_command(COMMAND_NAME, 'start', 'random_alias')

    def test_not_mutliplexed_index_raises(self):
        not_multiplexed = TestDocumentAdapter("name", "type")
        cname = "not_multi"
        adapter_cname_map[cname] = not_multiplexed
        try:
            with self.assertRaises(IndexNotMultiplexedException):
                call_command(COMMAND_NAME, 'start', cname)
        finally:
            del adapter_cname_map[cname]

    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.check_task_progress')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.ESSyncUtil.perform_cleanup')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.es_manager.reindex')
    def test_pass_multiplexed_index_raise_no_errors(self, sync_mock, cleanup_mock, _):
        sync_mock.return_value = "task_key:123"
        call_command(COMMAND_NAME, 'start', INDEX_CNAME)

    @patch("corehq.apps.es.utils.TASK_POLL_DELAY", 0)
    def test_reindex_command_copies_all_documents(self):
        self.adapter.primary.index(TestDoc('key_2', 'val'))
        self.adapter.primary.index(TestDoc('key', 'value'))

        # Test No documents present in secondary index
        self.assertEqual(
            self.adapter.secondary.count({}),
            0
        )
        manager.index_refresh(self.adapter.index_name)

        print("")  # improve test output when using --nocapture option
        call_command(COMMAND_NAME, 'start', INDEX_CNAME)
        manager.index_refresh(self.adapter.secondary.index_name)

        primary_index_docs = self.adapter.search({})['hits']['hits']
        secondary_index_docs = self.adapter.secondary.search({})['hits']['hits']

        primary_ids = {doc['_id'] for doc in primary_index_docs}
        secondary_ids = {doc['_id'] for doc in secondary_index_docs}

        # Test both the documents were copied successfully
        self.assertEqual(
            primary_ids,
            secondary_ids
        )
        self.assertEqual(
            self.adapter.secondary.count({}),
            2
        )
