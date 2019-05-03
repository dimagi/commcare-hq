from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
from unittest import SkipTest

from django.test import TestCase

from corehq.apps.userreports.models import CitusConfig
from corehq.apps.userreports.tests.utils import (
    doc_to_change,
    get_sample_data_source,
    get_sample_doc_and_indicators,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.pillows.case import get_case_pillow


class DataSourceConfigurationCitusDBTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data_source = get_sample_data_source()
        cls.data_source.engine_id = 'icds-ucr'
        for indicator in cls.data_source.configured_indicators:
            if indicator['column_id'] == 'owner':
                indicator['is_primary_key'] = True
        cls.data_source.sql_settings.citus_config = CitusConfig(
            distribution_type="hash",
            distribution_column="owner"
        )
        cls.data_source.sql_settings.primary_key = ['owner', 'doc_id']
        cls.adapter = get_indicator_adapter(cls.data_source)
        if not cls.adapter.session_helper.is_citus_db:
            raise SkipTest("Test only applicable when using CitusDB: {}".format(cls.adapter.session_helper.engine))

        # SkipTest must come before this setup so that the database is only setup if the test is not skipped
        super(DataSourceConfigurationCitusDBTest, cls).setUpClass()
        cls.data_source.save()
        cls.adapter.build_table()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.session_helper.Session.remove()
        cls.adapter.drop_table()
        cls.data_source.delete()
        super(DataSourceConfigurationCitusDBTest, cls).tearDownClass()

    def _process_docs(self, docs):
        pillow = get_case_pillow(ucr_configs=[self.data_source])

        for doc in docs:
            pillow.process_change(doc_to_change(doc))

    def test_distributed_table(self):
        sample_doc1, _ = get_sample_doc_and_indicators(owner_id='owner1')
        sample_doc1['opened_on'] = datetime(2018, 1, 1)
        sample_doc2, _ = get_sample_doc_and_indicators(owner_id='owner2')
        sample_doc2['opened_on'] = datetime(2018, 1, 2)

        self._process_docs([sample_doc1, sample_doc2])

        self.assertEqual(2, self.adapter.get_query_object().count())

        # extra checks to verify that the data is actually being distributed which may not be
        # necessary but is included for completeness

        # this assumes the records will be in different shards. This is safe
        # in unit tests since the #shards etc is static.
        with self.adapter.session_helper.engine.begin() as connection:
            owners_by_shard = {}
            for owner_id in ('owner1', 'owner2'):
                # determine which shard each record is in
                res = connection.execute("""
                    SELECT shardid
                    FROM pg_dist_placement AS placement
                    WHERE shardid = (
                        SELECT get_shard_id_for_distribution_column(%(table)s, %(value)s)
                    );
                """, {
                    'table': self.adapter.get_table().name,
                    'value': owner_id
                })
                for row in res:
                    owners_by_shard[row.shardid] = owner_id

            # for each shard get the owner ID
            # this only works if there is a single row per shard which is true in this case
            res = connection.execute("""
                SELECT *
                FROM run_command_on_shards(%(table)s, $cmd$
                  SELECT owner from %%s;
                $cmd$);
            """, {'table': self.adapter.get_table().name})
            shard_data = {}
            for row in res:
                shard_data[row.shardid] = row.result

        for shardid, owner_id in owners_by_shard.items():
            self.assertEqual(owner_id, shard_data[shardid])
