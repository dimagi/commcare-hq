import uuid
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

import corehq.apps.es.const as es_consts
from corehq.apps.es import app_adapter, case_adapter, case_search_adapter
from corehq.apps.es.client import (
    ElasticMultiplexAdapter,
    create_document_adapter,
    manager,
)
from corehq.apps.es.const import HQ_APPS_INDEX_CANONICAL_NAME
from corehq.apps.es.exceptions import (
    IndexAlreadySwappedException,
    IndexMultiplexedException,
    IndexNotMultiplexedException,
)
from corehq.apps.es.management.commands.elastic_sync_multiplexed import (
    ESSyncUtil,
)
from corehq.apps.es.tests.utils import TestDoc, TestDocumentAdapter, es_test
from corehq.pillows.case import get_case_pillow
from corehq.util.test_utils import create_and_save_a_case
from testapps.test_pillowtop.utils import process_pillow_changes

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


def _get_patched_adapter(adapter, multiplex_index, swap_index, secondary=None):
    """
    Since adapter are initialized while Django boots up, so overriding settings won't
    return the required adapter config for test. This function would create the adapter with required
    overridden settings.
    """
    cname = adapter.canonical_name
    multiplex_setting_key = f"ES_{cname.upper()}_INDEX_MULTIPLEXED"
    swap_setting_key = f"ES_{cname.upper()}_INDEX_SWAPPED"
    adapter_cls = adapter.__class__
    if isinstance(adapter, ElasticMultiplexAdapter):
        adapter_cls = adapter.primary.__class__
    # strip of test_ from index names because create_document_adapter will append it again for tests
    index_name = adapter.index_name[5:] if adapter.index_name.startswith('test_') else adapter.index_name
    with override_settings(**{multiplex_setting_key: multiplex_index, swap_setting_key: swap_index}):
        patched_adapter = create_document_adapter(
            adapter_cls, index_name,
            adapter.type, secondary=secondary
        )
    return patched_adapter


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

    def tearDown(self) -> None:
        manager.cluster_routing(enabled=True)
        return super().tearDown()

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
        adapter_patch.return_value = _get_patched_adapter(app_adapter, True, False, secondary='app_secondary')
        with self.assertRaises(IndexMultiplexedException):
            ESSyncUtil().delete_index(HQ_APPS_INDEX_CANONICAL_NAME)

    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_raises_if_index_not_swapped(self, adapter_patch):
        adapter_patch.return_value = _get_patched_adapter(
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
        'test_apps-20230524'
    )
    @patch('builtins.input', return_value='N')
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_fails_for_incorrect_user_input(self, adapter_patch, input_patch):
        secondary_index_name = 'test_apps_secondary'
        # This will return adapter with ``secondary_index_name`` because swapped is set to True
        patched_adapter = _get_patched_adapter(app_adapter, False, True, secondary=secondary_index_name[5:])
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
        'test_apps-20230524'
    )
    @patch('builtins.input', return_value=HQ_APPS_INDEX_CANONICAL_NAME)
    @patch('corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname')
    def test_delete_index_deletes_the_older_index(self, adapter_patch, input_patch):
        secondary_index_name = 'test_apps_secondary'
        # This will return adapter with ``secondary_index_name`` because swapped is set to True
        patched_adapter = _get_patched_adapter(app_adapter, False, True, secondary=secondary_index_name[5:])
        adapter_patch.return_value = patched_adapter
        self._setup_indexes([app_adapter.index_name, secondary_index_name])
        self.addCleanup(self._delete_indexes, [secondary_index_name])

        ESSyncUtil().delete_index(HQ_APPS_INDEX_CANONICAL_NAME)
        self.assertFalse(manager.index_exists(app_adapter.index_name))

    def test_remove_residual_indices_does_not_remove_known_indices(self):
        util = ESSyncUtil()

        # Create known HQ indices if they don't exist
        existing_index_names = util._get_all_known_index_names()
        for index in existing_index_names:
            # We are testing for actual index names, they might exist on local system
            # So we testing if they exist first.
            if not manager.index_exists(index):
                manager.index_create(index)
                self.addCleanup(manager.index_delete, index)

        util.remove_residual_indices()
        for index in existing_index_names:
            self.assertTrue(manager.index_exists(index))

    def test_remove_residual_indices_remove_closed_indices(self):
        util = ESSyncUtil()

        # Create an index and close it
        type_ = "test_doc"
        mappings = {"properties": {"value": {"type": "text"}}}
        settings = {
            "number_of_replicas": "0",
            "number_of_shards": "1",
        }
        closed_index_name = 'closed_index'
        manager.index_create(closed_index_name, {"mappings": {type_: mappings}, "settings": settings})

        # Index a doc before closing it
        manager._es.index(closed_index_name, doc_type=type_, body={'value': 'a test doc'}, id="1234", timeout='5m')
        manager.index_close(closed_index_name)

        # Ensure the closed index exist
        self.assertTrue(manager.index_exists(closed_index_name))

        with patch('builtins.input', return_value=closed_index_name):
            util.remove_residual_indices()

        # Assert Residual indices are deleted
        self.assertFalse(manager.index_exists(closed_index_name))

    def test_remove_residual_indices_removes_unknown_indices(self):
        util = ESSyncUtil()

        # Create known HQ indices if they don't exist
        existing_index_names = util._get_all_known_index_names()
        for index in existing_index_names:
            # We are testing for actual index names, they might exist on local system
            # So we testing if they exist first.
            if not manager.index_exists(index):
                manager.index_create(index)
                self.addCleanup(manager.index_delete, index)

        # Create some residual indices
        type_ = "test_doc"
        mappings = {"properties": {"value": {"type": "text"}}}
        settings = {
            "number_of_replicas": "0",
            "number_of_shards": "1",
        }
        residual_index_names = ['closed_index', 'index_1', 'index_2']
        for index in residual_index_names:
            manager.index_create(index, {"mappings": {type_: mappings}, "settings": settings})

        # Create a closed index too
        manager._es.index(residual_index_names[0], doc_type=type_, body={'value': 'a test doc'}, id="1234")
        manager.index_close(residual_index_names[0])

        # Ensure all indices exists
        for index in residual_index_names:
            self.assertTrue(manager.index_exists(index))

        with patch('builtins.input', side_effect=residual_index_names):
            util.remove_residual_indices()

        # Assert Residual indices are deleted
        for index in residual_index_names:
            self.assertFalse(manager.index_exists(index))

        # Assert existing indices are not deleted
        for index in existing_index_names:
            self.assertTrue(manager.index_exists(index))

    def _setup_indexes(self, indexes):
        for index in indexes:
            manager.index_create(index)

    def _delete_indexes(self, indexes):
        for index in indexes:
            manager.index_delete(index)


@es_test(
    requires=[
        _get_patched_adapter(case_adapter, True, False, 'test_cases_secondary'),
        _get_patched_adapter(case_search_adapter, True, False, 'test_casesearch_secondary')
    ],
    setup_class=True
)
class TestCopyCheckpointsBeforeIndexSwap(TestCase):

    def test_set_checkpoints_for_new_index_raises_on_non_multiplexed_index(self):
        patched_case_adapter = _get_patched_adapter(case_adapter, False, False)
        with patch(
            'corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname',
            return_value=patched_case_adapter
        ):
            with self.assertRaises(IndexNotMultiplexedException):
                ESSyncUtil().set_checkpoints_for_new_index('cases')

    @override_settings(ES_CASES_INDEX_SWAPPED=True)
    def test_set_checkpoints_for_new_index_raises_swapped_multiplexed_index(self):
        patched_case_adapter = _get_patched_adapter(case_adapter, True, True, 'second-index')
        with patch(
            'corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname',
            return_value=patched_case_adapter
        ):
            with self.assertRaises(IndexAlreadySwappedException):
                ESSyncUtil().set_checkpoints_for_new_index('cases')

    @override_settings(ES_CASES_INDEX_MULTIPLEXED=True)
    def test_set_checkpoints_for_new_index(self):

        secondary_case_index = 'cases_secondary'

        # Use patched case adapter with only multiplexer turned on
        patched_case_adapter = _get_patched_adapter(case_adapter, True, False, secondary_case_index)
        with (
            patch.object(es_consts, 'HQ_CASES_SECONDARY_INDEX_NAME', secondary_case_index),
            patch('corehq.pillows.case.case_adapter', patched_case_adapter)
        ):

            domain = 'test_checkpoint_copy'

            # Create a case pillow using the patched case adapter
            case_pillow = get_case_pillow(skip_ucr=True)

            # Save initial checkpoints
            initial_checkpoints = case_pillow.checkpoint.get_current_sequence_as_dict()

            # Save a case and propogate the changes to the pillow
            with process_pillow_changes(case_pillow):
                with process_pillow_changes('DefaultChangeFeedPillow'):
                    create_and_save_a_case(domain, case_id=uuid.uuid4().hex, case_name='test case')

            # Save the checkpoints after case is processed
            updated_checkpoints = case_pillow.checkpoint.get_current_sequence_as_dict()

            # After processing the form,  the checkpoints should have been updated
            self.assertNotEqual(initial_checkpoints, updated_checkpoints)

            # Call the utility to set checkpoints for new index.
            with patch(
                'corehq.apps.es.management.commands.elastic_sync_multiplexed.get_all_pillow_instances',
                return_value=[case_pillow]
            ), patch(
                'corehq.apps.es.management.commands.elastic_sync_multiplexed.doc_adapter_from_cname',
                return_value=patched_case_adapter
            ):
                ESSyncUtil().set_checkpoints_for_new_index('cases')

        # Swap indexes and patch adapter to return multiplexed adapter
        # with secondary index as main index
        patched_case_adapter = _get_patched_adapter(case_adapter, True, True, secondary_case_index)
        with (
            patch.object(es_consts, 'HQ_CASES_SECONDARY_INDEX_NAME', secondary_case_index),
            patch('corehq.pillows.case.case_adapter', patched_case_adapter)
        ):
            case_pillow = get_case_pillow(skip_ucr=True)

            # Save checkpoints for the new index
            new_index_checkpoints = case_pillow.checkpoint.get_current_sequence_as_dict()

        # Checkpoints for new index should match the checkpoints from previous index
        self.assertEqual(updated_checkpoints, new_index_checkpoints)
