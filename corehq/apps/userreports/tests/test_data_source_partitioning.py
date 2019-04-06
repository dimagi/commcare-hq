from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
from django.test import TestCase

from corehq.apps.userreports.models import SQLPartition
from corehq.apps.userreports.tests.utils import (
    doc_to_change,
    get_sample_data_source,
    get_sample_doc_and_indicators,
)
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.pillows.case import get_case_pillow


EXPECTED_UCR_CHILD_TABLE_PREFIX = 'tbl_8e3a5ee0a4309ee52345c2cdcbb1215a_'


class DataSourceConfigurationPartitionTest(TestCase):
    column = None
    subtype = None
    constraint = None

    @classmethod
    def setUpClass(cls):
        super(DataSourceConfigurationPartitionTest, cls).setUpClass()
        cls.data_source = get_sample_data_source()
        cls.data_source.sql_settings.partition_config = [
            SQLPartition(column=cls.column, subtype=cls.subtype, constraint=cls.constraint)
        ]
        cls.data_source.save()
        cls.adapter = get_indicator_adapter(cls.data_source)
        cls.adapter.build_table()

    def tearDown(self):
        self.adapter.session_helper.Session.remove()
        table = self.adapter.get_table()
        self.adapter.engine.execute("DROP TABLE \"%s\" CASCADE;" % table.name)
        self.data_source.delete()
        super(DataSourceConfigurationPartitionTest, self).tearDown()

    def _process_docs(self, docs):
        pillow = get_case_pillow(ucr_configs=[self.data_source])

        for doc in docs:
            pillow.process_change(doc_to_change(doc))


class DataSourcePartitionByDay(DataSourceConfigurationPartitionTest):
    column = "date"
    subtype = "date"
    constraint = "day"

    def test_partitioned_by_date(self):
        # two docs from separate days
        sample_doc1, _ = get_sample_doc_and_indicators()
        sample_doc1['opened_on'] = datetime(2018, 1, 1)
        sample_doc2, _ = get_sample_doc_and_indicators()
        sample_doc2['opened_on'] = datetime(2018, 1, 2)

        self._process_docs([sample_doc1, sample_doc2])

        self.assertEqual(2, self.adapter.get_query_object().count())

        # ensure docs are in separate databases
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}y2018d001";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]
        self.assertEqual(1, result)
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}y2018d002";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]
        self.assertEqual(1, result)


class DataSourcePartitionByMonth(DataSourceConfigurationPartitionTest):
    column = "date"
    subtype = "date"
    constraint = "month"

    def test_partitioned_by_date(self):
        # two docs from separate days
        sample_doc1, _ = get_sample_doc_and_indicators()
        sample_doc1['opened_on'] = datetime(2018, 1, 1)
        sample_doc2, _ = get_sample_doc_and_indicators()
        sample_doc2['opened_on'] = datetime(2018, 2, 2)
        sample_doc3, _ = get_sample_doc_and_indicators()
        sample_doc3['opened_on'] = datetime(2018, 2, 3)

        self._process_docs([sample_doc1, sample_doc2, sample_doc3])

        self.assertEqual(3, self.adapter.get_query_object().count())

        # ensure docs are in separate databases
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}y2018m01";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]

        self.assertEqual(1, result)
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}y2018m02";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]
        self.assertEqual(2, result)


class DataSourcePartitionByOwner(DataSourceConfigurationPartitionTest):
    column = "owner"
    subtype = "string_firstchars"
    constraint = "10"

    def test_partitioned_by_date(self):
        # two docs from separate days
        sample_doc1, _ = get_sample_doc_and_indicators()
        sample_doc1['owner_id'] = "abcdefghijklmnop"
        sample_doc2, _ = get_sample_doc_and_indicators()
        sample_doc2['owner_id'] = "abcdefghijklmnop"

        # drop g
        sample_doc3, _ = get_sample_doc_and_indicators()
        sample_doc3['owner_id'] = "abcdefhijklmnop"

        self._process_docs([sample_doc1, sample_doc2, sample_doc3])

        self.assertEqual(3, self.adapter.get_query_object().count())

        # ensure docs are in separate databases
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}abcdefghij";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]

        self.assertEqual(2, result)
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}abcdefhijk";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]
        self.assertEqual(1, result)


class DataSourcePartitionByOwnerLastChars(DataSourceConfigurationPartitionTest):
    column = "owner"
    subtype = "string_lastchars"
    constraint = "10"

    def test_partitioned_by_date(self):
        # two docs from separate days
        sample_doc1, _ = get_sample_doc_and_indicators()
        sample_doc1['owner_id'] = "abcdefghijklmnop"
        sample_doc2, _ = get_sample_doc_and_indicators()
        sample_doc2['owner_id'] = "abcdefghijklmnop"

        # drop g
        sample_doc3, _ = get_sample_doc_and_indicators()
        sample_doc3['owner_id'] = "abcdefhijklmnop"

        self._process_docs([sample_doc1, sample_doc2, sample_doc3])

        self.assertEqual(3, self.adapter.get_query_object().count())

        # ensure docs are in separate databases
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}ghijklmnop";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]

        self.assertEqual(2, result)
        result = self.adapter.engine.execute(
            'SELECT COUNT(*) FROM "{}fhijklmnop";'.format(EXPECTED_UCR_CHILD_TABLE_PREFIX))
        result = result.fetchone()[0]
        self.assertEqual(1, result)
