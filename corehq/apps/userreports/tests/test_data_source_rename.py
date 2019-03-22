from __future__ import absolute_import
from __future__ import unicode_literals

import uuid
from datetime import datetime

import mock
import sqlalchemy
from django.test import TestCase
from mock import MagicMock, patch
from sqlalchemy.engine import reflection

from corehq.apps.userreports.management.commands.rename_ucr_tables import create_ucr_views
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql.adapter import build_table, get_indicator_table
from corehq.apps.userreports.sql.util import table_exists, view_exists
from corehq.apps.userreports.tests.utils import (
    doc_to_change,
    get_sample_data_source,
    get_sample_doc_and_indicators,
)
from corehq.apps.userreports.util import get_indicator_adapter, get_legacy_table_name
from corehq.pillows.case import get_case_pillow


class DataSourceRenameTest(TestCase):

    @patch('corehq.apps.callcenter.data_source.get_call_center_domains', MagicMock(return_value=[]))
    def setUp(self):
        super(DataSourceRenameTest, self).setUp()
        self.data_source = get_sample_data_source()
        self.data_source.table_id = self.data_source.table_id + uuid.uuid4().hex[-8:]
        self.data_source.save()
        self.adapter = get_indicator_adapter(self.data_source)
        self.old_table_name = get_legacy_table_name(
            self.data_source.domain, self.data_source.table_id,
        )
        # use custom metadata here so that the table doesn't end up in the global metadata
        self.old_table = get_indicator_table(
            self.data_source, sqlalchemy.MetaData(), override_table_name=self.old_table_name
        )
        build_table(self.adapter.engine, self.old_table)
        create_ucr_views()

    def tearDown(self):
        self.adapter.session_helper.Session.remove()
        self.adapter.drop_table()
        self.data_source.delete()
        self.adapter._drop_legacy_table_and_view()
        super(DataSourceRenameTest, self).tearDown()

    def _process_docs(self, docs):
        pillow = get_case_pillow(ucr_configs=[self.data_source])

        for doc in docs:
            pillow.process_change(doc_to_change(doc))

    def test_write_and_query_view(self):
        sample_doc1, _ = get_sample_doc_and_indicators(owner_id='owner1')
        sample_doc1['opened_on'] = datetime(2018, 1, 1)
        sample_doc2, _ = get_sample_doc_and_indicators(owner_id='owner2')
        sample_doc2['opened_on'] = datetime(2018, 1, 2)

        self._process_docs([sample_doc1, sample_doc2])

        self.assertEqual(2, self.adapter.get_query_object().count())
        self.assertEqual(2, self.adapter.session_helper.Session.query(self.old_table).count())

    def test_rebuild(self):
        self.adapter.rebuild_table()
        with self.adapter.engine.begin() as conn:
            old_table_exists = table_exists(conn, self.old_table.name)
            table_view_exists = view_exists(conn, self.adapter.get_table().name)

        self.assertFalse(old_table_exists)
        self.assertFalse(table_view_exists)

    def test_add_nullable_column(self):
        # assert new date isn't in the config
        insp = reflection.Inspector.from_engine(self.adapter.engine)
        self.assertEqual(
            len([c for c in insp.get_columns(self.old_table.name) if c['name'] == 'new_date']), 0
        )

        # add the column to the config
        self.data_source.configured_indicators.append({
            "column_id": "new_date",
            "type": "raw",
            "display_name": "new_date opened",
            "datatype": "datetime",
            "property_name": "other_opened_on",
            "is_nullable": True
        })
        self.data_source.save()
        # re-fetch to clear memoized properties
        self.data_source = DataSourceConfiguration.get(self.data_source._id)

        # mock rebuild table to ensure the column is added without rebuild table
        with mock.patch('corehq.apps.userreports.pillow.ConfigurableReportPillowProcessor.rebuild_table'):
            pillow = get_case_pillow(ucr_configs=[self.data_source])
            self.assertFalse(pillow.processors[0].rebuild_table.called)
        insp = reflection.Inspector.from_engine(self.adapter.engine)
        self.assertEqual(
            len([c for c in insp.get_columns(self.old_table.name) if c['name'] == 'new_date']), 1
        )
