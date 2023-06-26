from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from corehq.apps.es import app_adapter
from corehq.apps.es.client import (
    ElasticMultiplexAdapter,
    create_document_adapter,
    manager,
)
from corehq.apps.es.const import HQ_APPS_INDEX_CANONICAL_NAME
from corehq.apps.es.exceptions import (
    IndexMultiplexedException,
    IndexNotMultiplexedException,
)
from corehq.apps.es.management.commands.elastic_sync_multiplexed import (
    ESSyncUtil,
)
from corehq.apps.es.tests.utils import TestDoc, TestDocumentAdapter, es_test

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


@es_test
class TestESSyncUtil(SimpleTestCase):

    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_fails_on_multiplexed_index(self, adapter_patch):
        adapter_patch.return_value = self._get_patched_adapter(app_adapter, True, False, secondary='app_secondary')
        with self.assertRaises(IndexMultiplexedException):
            ESSyncUtil().delete_index(HQ_APPS_INDEX_CANONICAL_NAME)

    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_raises_if_index_not_swapped(self, adapter_patch):
        adapter_patch.return_value = self._get_patched_adapter(
            app_adapter, False, False, secondary='app_secondary'
        )
        with self.assertRaises(AssertionError):
            ESSyncUtil().delete_index(HQ_APPS_INDEX_CANONICAL_NAME)

    @patch(
        'corehq.apps.es.management.commands.elastic_sync_multiplexed.es_consts.HQ_APPS_SECONDARY_INDEX_NAME',
        'test_apps_secondary'
    )
    @patch(
        'corehq.apps.es.management.commands.elastic_sync_multiplexed.es_consts.HQ_APPS_INDEX_NAME',
        'test_hqapps_2020-02-26'
    )
    @patch('builtins.input', return_value='N')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_fails_for_incorrect_user_input(self, adapter_patch, input_patch):
        secondary_index_name = 'test_apps_secondary'
        # This will return adapter with ``secondary_index_name`` because swapped is set to True
        patched_adapter = self._get_patched_adapter(app_adapter, False, True, secondary=secondary_index_name[5:])
        adapter_patch.return_value = patched_adapter
        input_patch.return_value = 'N'
        self._setup_indexes([app_adapter.index_name, secondary_index_name])
        self.addCleanup(self._delete_indexes, [app_adapter.index_name, secondary_index_name])

        with self.assertRaises(CommandError):
            ESSyncUtil().delete_index(HQ_APPS_INDEX_CANONICAL_NAME)

    @patch(
        'corehq.apps.es.management.commands.elastic_sync_multiplexed.es_consts.HQ_APPS_SECONDARY_INDEX_NAME',
        'test_apps_secondary'
    )
    @patch(
        'corehq.apps.es.management.commands.elastic_sync_multiplexed.es_consts.HQ_APPS_INDEX_NAME',
        'test_hqapps_2020-02-26'
    )
    @patch('builtins.input', return_value='N')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_deletes_the_older_index(self, adapter_patch, input_patch):
        secondary_index_name = 'test_apps_secondary'
        # This will return adapter with ``secondary_index_name`` because swapped is set to True
        patched_adapter = self._get_patched_adapter(app_adapter, False, True, secondary=secondary_index_name[5:])
        adapter_patch.return_value = patched_adapter
        input_patch.return_value = 'y'
        self._setup_indexes([app_adapter.index_name, secondary_index_name])
        self.addCleanup(self._delete_indexes, [secondary_index_name])

        ESSyncUtil().delete_index(HQ_APPS_INDEX_CANONICAL_NAME)
        self.assertFalse(manager.index_exists(app_adapter.index_name))

    def _get_patched_adapter(self, adapter, multiplex_index, swap_index, secondary=None):
        """
        Since adapter are initialized while Django boots up, so overriding settings won't
        return the required adapter config for test. This function would create the adapter with required
        overridden settings.
        """
        cname = adapter.canonical_name
        multiplex_setting_key = f"ES_{cname.upper()}_INDEX_MULTIPLEXED"
        swap_setting_key = f"ES_{cname.upper()}_INDEX_SWAPPED"
        adapter_cls = app_adapter.__class__
        if isinstance(app_adapter, ElasticMultiplexAdapter):
            adapter_cls = app_adapter.primary.__class__
        # strip of test_ from index names because create_document_adapter will append it again for tests
        index_name = adapter.index_name[5:] if adapter.index_name.startswith('test_') else adapter.index_name
        with override_settings(**{multiplex_setting_key: multiplex_index, swap_setting_key: swap_index}):
            patched_adapter = create_document_adapter(
                adapter_cls, index_name,
                adapter.type, secondary=secondary
            )
        return patched_adapter

    def _setup_indexes(self, indexes):
        for index in indexes:
            manager.index_create(index)

    def _delete_indexes(self, indexes):
        for index in indexes:
            manager.index_delete(index)
