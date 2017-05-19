from mock import patch
from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.groups.models import Group

from corehq.warehouse.models import (
    GroupStagingTable
)


class TestGroupStagingTable(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.groups = [
            Group(name='one', case_sharing=True, reporting=True),
            Group(name='two'),
            Group(name='three'),
        ]
        for group in cls.groups:
            group.save()

    def tearDown(self):
        GroupStagingTable.clear_records()

    @classmethod
    def tearDownClass(cls):
        for group in cls.groups:
            group.delete()

    def test_stage_records(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        self.assertEqual(GroupStagingTable.objects.count(), 0)
        GroupStagingTable.stage_records(start, end)
        self.assertEqual(GroupStagingTable.objects.count(), 3)

        GroupStagingTable.stage_records(start, end)
        self.assertEqual(GroupStagingTable.objects.count(), 3)

    def test_stage_records_no_data(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() - timedelta(days=2)

        self.assertEqual(GroupStagingTable.objects.count(), 0)
        GroupStagingTable.stage_records(start, end)
        self.assertEqual(GroupStagingTable.objects.count(), 0)

    def test_stage_records_bulk(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        # 2 Queries for the atomic.transaction
        # 1 Query for clearing records
        # 1 Query for inserting recorrds
        with self.assertNumQueries(4):
            GroupStagingTable.stage_records(start, end)

        # 2 Queries for the atomic.transaction
        # 1 Query for clearing records
        # 2 Queries for inserting recorrds
        with self.assertNumQueries(5):
            with patch('corehq.warehouse.utils.DJANGO_MAX_BATCH_SIZE', 2):
                GroupStagingTable.stage_records(start, end)
        self.assertEqual(GroupStagingTable.objects.count(), 3)
