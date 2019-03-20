from __future__ import absolute_import
from __future__ import unicode_literals

import mock
from django.test import TestCase
from sqlalchemy.engine import reflection

from corehq.apps.userreports.tests.utils import get_sample_data_source
from corehq.apps.userreports.util import get_indicator_adapter, get_table_name
from corehq.pillows.case import get_case_pillow


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
        self.assertEqual(len(insp.get_indexes(table_name)), 0)

        # add the index to the config
        config = self._get_config('add_index')
        self.addCleanup(config.delete)
        config.configured_indicators[0]['create_index'] = True
        config.save()
        adapter = get_indicator_adapter(config)

        # mock rebuild table to ensure the table isn't rebuilt when adding index
        pillow = get_case_pillow(ucr_configs=[config])
        pillow.processors[0].rebuild_table = mock.MagicMock()
        pillow.processors[0].bootstrap([config])

        self.assertFalse(pillow.processors[0].rebuild_table.called)
        engine = adapter.engine
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(len(insp.get_indexes(table_name)), 1)

    def test_add_non_nullable_column(self):
        self._setup_data_source('add_non_nullable_col')

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0
        )

        # add the column to the config
        config = self._get_config('add_non_nullable_col')
        self.addCleanup(config.delete)
        config.configured_indicators.append({
            "column_id": "new_date",
            "type": "raw",
            "display_name": "new_date opened",
            "datatype": "datetime",
            "property_name": "other_opened_on",
            "is_nullable": False
        })
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine

        # mock rebuild table to ensure the table is rebuilt
        with mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.rebuild_table'):
            pillow = get_case_pillow(ucr_configs=[config])
            self.assertTrue(pillow.processors[0].rebuild_table.called)
        # column doesn't exist because rebuild table was mocked
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0
        )

        # Another time without the mock to ensure the column is there
        pillow = get_case_pillow(ucr_configs=[config])
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1
        )

    def test_add_nullable_column(self):
        self._setup_data_source('add_nullable_col')

        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 0
        )

        # add the column to the config
        config = self._get_config('add_nullable_col')
        self.addCleanup(config.delete)
        config.configured_indicators.append({
            "column_id": "new_date",
            "type": "raw",
            "display_name": "new_date opened",
            "datatype": "datetime",
            "property_name": "other_opened_on",
            "is_nullable": True
        })
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine

        # mock rebuild table to ensure the column is added without rebuild table
        pillow = get_case_pillow(ucr_configs=[config])
        pillow.processors[0].rebuild_table = mock.MagicMock()
        self.assertFalse(pillow.processors[0].rebuild_table.called)
        insp = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            len([c for c in insp.get_columns(table_name) if c['name'] == 'new_date']), 1
        )

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
        config.configured_indicators.append({
            "column_id": "pk_key",
            "type": "raw",
            "datatype": "string",
            "property_name": "owner_id",
            "is_primary_key": True
        })
        config.save()
        adapter = get_indicator_adapter(config)
        engine = adapter.engine
        config.sql_settings.primary_key = ['pk_key', 'doc_id']

        # rebuild table
        get_case_pillow(ucr_configs=[config])
        insp = reflection.Inspector.from_engine(engine)
        table_name = get_table_name(self.config.domain, self.config.table_id)
        pk = insp.get_pk_constraint(table_name)
        expected_pk = ['pk_key', 'doc_id']
        self.assertEqual(expected_pk, pk['constrained_columns'])
