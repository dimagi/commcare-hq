from unittest import mock

from django.test import TestCase

from sqlalchemy.engine import reflection

from corehq.apps.userreports.indicators import Column, RawIndicator
from corehq.apps.userreports.models import (
    DataSourceActionLog,
    DataSourceConfiguration,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_data_source,
    skip_domain_filter_patch,
)
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.pillows.case import get_case_pillow
from corehq.util.test_utils import softer_assert


def setup_module():
    skip_domain_filter_patch.start()


def teardown_module():
    skip_domain_filter_patch.stop()


class RebuildTableTest(TestCase):
    """This test is pretty fragile because in UCRs we have a global metadata
    object that sqlalchemy uses to keep track of tables and indexes. I've attempted
    to work around it here, but it feels a little nasty
    """

    def tearDown(self):
        self.adapter.drop_table()
        self.config.delete()

    def _get_config(self, extra_id):
        config = get_sample_data_source()
        config.table_id = config.table_id + extra_id
        return config

    def _setup_data_source(self, extra_id):
        self.config = self._get_config(extra_id)
        self.config.save()
        get_case_pillow(ucr_configs=[self.config])
        self.adapter = get_indicator_adapter(self.config)
        self.engine = self.adapter.engine

    def test_add_index(self):
        # build the table without an index
        self._setup_data_source('add_index')

        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(
            len(insp.get_indexes(table_name)), 1
        )  # index on `inserted_at` column

        # add the index to the config
        config = self._get_config('add_index')
        self.addCleanup(config.delete)
        config.configured_indicators[0]['create_index'] = True
        config.save()
        adapter = get_indicator_adapter(config)

        with mock.patch(
            'corehq.apps.userreports.pillow_utils.rebuild_table'
        ) as rebuild_table, mock.patch(
            'corehq.apps.userreports.pillow_utils.migrate_tables_with_logging'
        ) as migrate_table:
            get_case_pillow(ucr_configs=[config])
            self.assertFalse(rebuild_table.called)
            self.assertTrue(migrate_table.called)

        engine = adapter.engine
        insp = reflection.Inspector.from_engine(engine)
        # note the index is not yet created
        self.assertEqual(len(insp.get_indexes(table_name)), 1)

    def test_table_with_inserted_at_index_excluded(self):
        def inserted_at_indicator_without_index_mock():
            return RawIndicator(
                'inserted at',
                Column(
                    id='inserted_at',
                    datatype='datetime',
                    is_nullable=False,
                    is_primary_key=False,
                ),
                getter=lambda doc, ctx: ctx.inserted_timestamp,
                wrapped_spec=None,
            )

        with mock.patch(
            'corehq.apps.userreports.models.DataSourceConfiguration._get_inserted_at_indicator'
        ) as get_inserted_at_indicator_mock:
            get_inserted_at_indicator_mock.return_value = (
                inserted_at_indicator_without_index_mock()
            )
            """Tables with indecies on `inserted_at` only should be excluded from being rebuilt"""
            self._setup_data_source('add_index')

        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        # Now that we mocked the `inserted_at` column to not have an index, the following should be true
        self.assertEqual(len(insp.get_indexes(table_name)), 0)

        config = self._get_config('add_index')
        # Make sure that the `inserted_at` column will now have the index
        inserted_at_indicator = list(
            filter(
                lambda indicator: isinstance(indicator, RawIndicator)
                and indicator.column.id == 'inserted_at',
                config.indicators.indicators,
            )
        )[0]
        self.assertEqual(inserted_at_indicator.column.id, 'inserted_at')
        self.assertTrue(inserted_at_indicator.column.create_index)

        self.addCleanup(config.delete)
        config.save()

        adapter = get_indicator_adapter(config)

        with mock.patch(
            'corehq.apps.userreports.pillow_utils.rebuild_table'
        ) as rebuild_table, mock.patch(
            'corehq.apps.userreports.pillow_utils.migrate_tables'
        ) as migrate_table:
            get_case_pillow(ucr_configs=[config])
            # Let's make sure a rebuild isn't triggered
            self.assertFalse(rebuild_table.called)

            # Let's make sure a migration isn't triggered
            args, _kwargs = migrate_table.call_args_list[0]
            engine, migration_diffs = args
            # `migration_diffs` should be empty, since the diff was filtered out
            self.assertEqual(migration_diffs, [])

        insp = reflection.Inspector.from_engine(adapter.engine)
        # Note: The index wasn't created, so this is still true
        self.assertEqual(len(insp.get_indexes(table_name)), 0)

    def test_add_non_nullable_column(self):
        self._setup_data_source('add_non_nullable_col')

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0)

        # add the column to the config
        config = self._get_config('add_non_nullable_col')
        self.addCleanup(config.delete)
        config.configured_indicators.append(
            {
                'column_id': 'new_date',
                'type': 'raw',
                'display_name': 'new_date opened',
                'datatype': 'datetime',
                'property_name': 'other_opened_on',
                'is_nullable': False,
            }
        )
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine

        # mock rebuild table to ensure the table is rebuilt
        with mock.patch(
            'corehq.apps.userreports.pillow_utils.rebuild_table'
        ) as rebuild_table:
            get_case_pillow(ucr_configs=[config])
            self.assertTrue(rebuild_table.called)
        # column doesn't exist because rebuild table was mocked
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0)

        # Another time without the mock to ensure the column is there
        get_case_pillow(ucr_configs=[config])
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1)

    def test_add_nullable_column(self):
        self._setup_data_source('add_nullable_col')

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0)

        # add the column to the config
        config = self._get_config('add_nullable_col')
        self.addCleanup(config.delete)
        config.configured_indicators.append(
            {
                'column_id': 'new_date',
                'type': 'raw',
                'display_name': 'new_date opened',
                'datatype': 'datetime',
                'property_name': 'other_opened_on',
                'is_nullable': True,
            }
        )
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine

        # mock rebuild table to ensure the column is added without rebuild table
        with mock.patch(
            'corehq.apps.userreports.pillow_utils.rebuild_table'
        ) as rebuild_table:
            get_case_pillow(ucr_configs=[config])
            self.assertFalse(rebuild_table.called)
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1)

    @softer_assert()
    def test_skip_destructive_rebuild(self):
        self.config = self._get_config('add_non_nullable_col')
        self.config.disable_destructive_rebuild = True
        self.config.save()

        get_case_pillow(ucr_configs=[self.config])
        self.adapter = get_indicator_adapter(self.config)
        self.engine = self.adapter.engine

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0)

        # re-fetch from DB to bust object caches
        self.config = DataSourceConfiguration.get(self.config.data_source_id)

        # add the column to the config
        self.config.configured_indicators.append(
            {
                'column_id': 'new_date',
                'type': 'raw',
                'display_name': 'new_date opened',
                'datatype': 'datetime',
                'property_name': 'other_opened_on',
                'is_nullable': False,
            }
        )
        self.config.save()

        # re-fetch from DB to bust object caches
        self.config = DataSourceConfiguration.get(self.config.data_source_id)

        # bootstrap to trigger rebuild
        get_case_pillow(ucr_configs=[self.config])

        logs = DataSourceActionLog.objects.filter(
            indicator_config_id=self.config.data_source_id,
            skip_destructive=True,
        )
        self.assertEqual(1, len(logs))
        migration_diffs = logs[0].migration_diffs
        index_name = insp.get_indexes(table_name)[0]['name']
        self.assertEqual(migration_diffs[0], {'type': 'add_column', 'item_name': 'new_date'})
        self.assertEqual(migration_diffs[1], {'type': 'remove_index', 'item_name': index_name})
        self.assertEqual(migration_diffs[2]['type'], 'add_index')

        # make the column allow nulls and check that it gets applied (since is non-destructive)
        self.config.configured_indicators[-1]['is_nullable'] = True
        self.config.save()

        # re-fetch from DB to bust object caches
        self.config = DataSourceConfiguration.get(self.config.data_source_id)
        # make sure change made it
        self.assertEqual(
            True, self.config.configured_indicators[-1]['is_nullable']
        )

        # bootstrap to trigger rebuild
        get_case_pillow(ucr_configs=[self.config])

        # make sure we didn't add any more logs
        self.assertEqual(
            DataSourceActionLog.objects.filter(
                indicator_config_id=self.config.data_source_id,
                skip_destructive=True,
            ).count(),
            1,
        )
        # confirm the column was added to the table
        insp = reflection.Inspector.from_engine(self.engine)
        self.assertEqual(len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1)

    def test_implicit_pk(self):
        self._setup_data_source('implicit_pk')
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        pk = insp.get_pk_constraint(table_name)
        expected_pk = ['doc_id']
        self.assertEqual(expected_pk, pk['constrained_columns'])

    def test_ordered_pk(self):
        self._setup_data_source('ordered_pk')
        config = self._get_config('ordered_pk')
        config.configured_indicators.append(
            {
                'column_id': 'pk_key',
                'type': 'raw',
                'datatype': 'string',
                'property_name': 'owner_id',
                'is_primary_key': True,
            }
        )
        config.sql_settings.primary_key = ['pk_key', 'doc_id']
        config.save()

        get_case_pillow(ucr_configs=[config])
        adapter = get_indicator_adapter(config)
        engine = adapter.engine
        insp = reflection.Inspector.from_engine(engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        pk = insp.get_pk_constraint(table_name)
        expected_pk = ['pk_key', 'doc_id']
        self.assertEqual(expected_pk, pk['constrained_columns'])
