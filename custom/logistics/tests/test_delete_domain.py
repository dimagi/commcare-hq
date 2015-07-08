from django.test import TestCase
from corehq import Domain
from custom.logistics.models import StockDataCheckpoint, MigrationCheckpoint


class TestDeleteDomain(TestCase):

    def setUp(self):
        self.domain = Domain(name="test", is_active=True)
        self.domain.save()
        self.domain2 = Domain(name="test2", is_active=True)
        self.domain2.save()

        StockDataCheckpoint.objects.create(
            domain='test',
            api='test',
            limit=100,
            offset=0
        )

        StockDataCheckpoint.objects.create(
            domain='test2',
            api='test',
            limit=100,
            offset=0
        )

        MigrationCheckpoint.objects.create(
            domain='test',
            api='test',
            limit=100,
            offset=0
        )

        MigrationCheckpoint.objects.create(
            domain='test2',
            api='test',
            limit=100,
            offset=0
        )

    def test_pre_delete_signal_receiver(self):
        self.domain.delete()

        self.assertEqual(MigrationCheckpoint.objects.filter(domain='test').count(), 0)
        self.assertEqual(StockDataCheckpoint.objects.filter(domain='test').count(), 0)

        self.assertEqual(MigrationCheckpoint.objects.filter(domain='test2').count(), 1)
        self.assertEqual(StockDataCheckpoint.objects.filter(domain='test2').count(), 1)

    def tearDown(self):
        self.domain2.delete()
