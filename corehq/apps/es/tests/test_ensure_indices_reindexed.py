from unittest.mock import patch
from uuid import uuid4

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from corehq.apps.es import app_adapter
from corehq.apps.es.client import ElasticDocumentAdapter, manager
from corehq.apps.es.management.commands.ensure_indices_reindexed import \
    Command as EnsureIndicesReindexedCommand
from corehq.apps.es.migration_operations import CreateIndex
from corehq.apps.es.tests.test_client import patch_elastic_version


class TestEnsureIndicesReindexed(SimpleTestCase):
    def setUp(self):
        self.primary_index_name = 'primary_apps_index'
        self.secondary_index_name = 'secondary_apps_index'

        self._create_index(self.primary_index_name)
        self.addCleanup(manager.index_delete, self.primary_index_name)

        self._create_index(self.secondary_index_name)
        self.addCleanup(manager.index_delete, self.secondary_index_name)

        return super().setUp()

    def _create_index(self, index_name, adapter=app_adapter):
        CreateIndex(
            index_name, adapter.type, adapter.mapping,
            adapter.analysis, adapter.settings_key
        ).run()

    def _populate(self, entries, adapters):
        apps = []
        for i in range(entries):
            apps.append(app_adapter.model_cls(_id=str(uuid4())))
        for adapter in adapters:
            adapter.bulk_index(apps)
            manager.index_refresh(adapter.index_name)
            print(adapter.index_name, adapter.count({}))

    @patch.object(EnsureIndicesReindexedCommand, '_secondary_index_name')
    @patch.object(EnsureIndicesReindexedCommand, '_primary_index_name')
    def test_get_both_adapters_from_cname(self, primary_index_patch, secondary_index_patch):
        primary_index_patch.return_value = self.primary_index_name
        secondary_index_patch.return_value = self.secondary_index_name

        primary_adapter, secondary_adapter = EnsureIndicesReindexedCommand().get_both_adapters_for_cname('apps')

        self.assertIsInstance(primary_adapter, ElasticDocumentAdapter)
        self.assertEqual(primary_adapter.index_name, self.primary_index_name)
        self.assertIsInstance(secondary_adapter, ElasticDocumentAdapter)
        self.assertEqual(secondary_adapter.index_name, self.secondary_index_name)

    @patch.object(EnsureIndicesReindexedCommand, '_secondary_index_name')
    @patch.object(EnsureIndicesReindexedCommand, '_primary_index_name')
    def test_get_doc_count_delta_percent(self, primary_index_patch, secondary_index_patch):
        primary_index_patch.return_value = self.primary_index_name
        secondary_index_patch.return_value = self.secondary_index_name

        index_cname = 'apps'
        adapters = [primary_adapter, secondary_adapter] = (
            EnsureIndicesReindexedCommand().get_both_adapters_for_cname(index_cname)
        )
        self._populate(5, adapters)

        delta = EnsureIndicesReindexedCommand().get_doc_count_delta_percent(index_cname)
        self.assertEqual(delta, 0)

        self._populate(5, [primary_adapter])

        delta = EnsureIndicesReindexedCommand().get_doc_count_delta_percent(index_cname)
        self.assertEqual(delta, 50)

    @patch.object(EnsureIndicesReindexedCommand, 'get_doc_count_delta_percent')
    def test_is_doc_count_difference_reasonable_when_diff_is_0(self, patched_fn):
        patched_fn.return_value = 0

        self.assertTrue(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('apps')
        )

    @patch.object(EnsureIndicesReindexedCommand, 'get_doc_count_delta_percent')
    def test_is_doc_count_difference_reasonable_when_diff_is_not_0(self, patched_fn):
        patched_fn.return_value = 50

        self.assertFalse(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('apps')
        )

    @patch.object(EnsureIndicesReindexedCommand, 'get_doc_count_delta_percent')
    def test_is_doc_count_difference_reasonable_diff_gt_1_for_high_frequency_indices(self, patched_fn):
        patched_fn.return_value = 10

        self.assertFalse(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('case_search')
        )

    @patch.object(EnsureIndicesReindexedCommand, 'get_doc_count_delta_percent')
    def test_is_doc_count_difference_reasonable_diff_lt_1_for_high_frequency_indices(self, patched_fn):
        patched_fn.return_value = 1
        self.assertTrue(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('case_search')
        )

        patched_fn.return_value = 0.98
        self.assertTrue(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('case_search')
        )

    @patch.object(EnsureIndicesReindexedCommand, 'get_doc_count_delta_percent')
    def test_is_doc_count_difference_reasonable_diff_lt_1_for_rest_indices(self, patched_fn):
        patched_fn.return_value = 1
        self.assertFalse(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('apps')
        )

        patched_fn.return_value = 0.98
        self.assertFalse(
            EnsureIndicesReindexedCommand().is_doc_count_difference_reasonable('apps')
        )

    @patch.object(EnsureIndicesReindexedCommand, 'check_indices_are_consistent')
    def test_command_skips_if_current_es_version_greater(self, patched_fn):
        with patch_elastic_version(manager, "5"):
            call_command(
                'ensure_indices_reindexed', 2, 'http://somechangelog.com'
            )
        self.assertFalse(patched_fn.called)

    @patch.object(EnsureIndicesReindexedCommand, '_secondary_index_name')
    @patch.object(EnsureIndicesReindexedCommand, '_primary_index_name')
    def test_command_raises_if_indices_missing(self, primary_index_patch, secondary_index_patch):
        primary_index_patch.return_value = self.primary_index_name
        secondary_index_patch.return_value = self.secondary_index_name

        manager.index_delete(self.secondary_index_name)
        with patch_elastic_version(manager, "2"):
            with self.assertRaises(CommandError):
                call_command(
                    'ensure_indices_reindexed', 2, 'http://somechangelog.com'
                )
        # adding for the cleanup to continue error free
        self._create_index(self.secondary_index_name)

    @patch.object(EnsureIndicesReindexedCommand, '_secondary_index_name')
    @patch.object(EnsureIndicesReindexedCommand, '_primary_index_name')
    def test_command_do_not_raise_if_indices_count_match(self, primary_index_patch, secondary_index_patch):
        primary_index_patch.return_value = self.primary_index_name
        secondary_index_patch.return_value = self.secondary_index_name

        index_cname = 'apps'
        adapters = [primary_adapter, secondary_adapter] = (
            EnsureIndicesReindexedCommand().get_both_adapters_for_cname(index_cname)
        )
        self._populate(5, adapters)

        with patch_elastic_version(manager, "2"):
            call_command(
                'ensure_indices_reindexed', 2, 'http://somechangelog.com'
            )

    @patch.object(EnsureIndicesReindexedCommand, '_secondary_index_name')
    @patch.object(EnsureIndicesReindexedCommand, '_primary_index_name')
    def test_command_raises_if_indices_count_does_not_match(self, primary_index_patch, secondary_index_patch):
        primary_index_patch.return_value = self.primary_index_name
        secondary_index_patch.return_value = self.secondary_index_name

        index_cname = 'apps'
        adapters = [primary_adapter, secondary_adapter] = (
            EnsureIndicesReindexedCommand().get_both_adapters_for_cname(index_cname)
        )
        self._populate(5, adapters)

        self._populate(5, [primary_adapter])
        with patch_elastic_version(manager, "2"):
            with self.assertRaises(CommandError):
                call_command(
                    'ensure_indices_reindexed', 2, 'http://somechangelog.com'
                )
