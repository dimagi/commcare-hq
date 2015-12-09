from datetime import datetime
from django.test import TestCase
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import LocationType, Location
from corehq.apps.products.models import Product
from custom.ilsgateway.models import ProductAvailabilityData, DeliveryGroupReport, SupplyPointWarehouseRecord, \
    Alert, OrganizationSummary, GroupSummary, SupplyPointStatus, HistoricalLocationGroup, ReportRun, ILSNotes, \
    SupervisionDocument


class TestDeleteDomain(TestCase):

    def _create_data(self, domain_name):
        product = Product(domain=domain_name, name='test-product')
        product.save()

        location = Location(
            domain=domain_name,
            site_code='testcode',
            name='test1',
            location_type='facility'
        )
        location.save()
        self.locations[domain_name] = location.get_id

        DeliveryGroupReport.objects.create(
            location_id=location.get_id,
            quantity=1,
            message='test',
            delivery_group='A'
        )

        SupplyPointWarehouseRecord.objects.create(
            supply_point=location.get_id,
            create_date=datetime.utcnow()
        )

        Alert.objects.create(
            text='test',
            expires=datetime.utcnow(),
            date=datetime.utcnow(),
            location_id=location.get_id
        )

        organization_summary = OrganizationSummary.objects.create(
            date=datetime.utcnow(),
            location_id=location.get_id
        )

        GroupSummary.objects.create(
            org_summary=organization_summary
        )

        ProductAvailabilityData.objects.create(
            product=product.get_id,
            date=datetime.utcnow(),
            location_id=location.get_id
        )

        SupplyPointStatus.objects.create(
            location_id=location.get_id,
            status_type='del_fac',
            status_value='received'
        )

        HistoricalLocationGroup.objects.create(
            location_id=location.sql_location,
            group='A',
            date=datetime.utcnow().date()
        )

        ReportRun.objects.create(
            domain=domain_name,
            start=datetime.utcnow(),
            end=datetime.utcnow(),
            start_run=datetime.utcnow()
        )

        ILSNotes.objects.create(
            location=location.sql_location,
            domain=domain_name,
            user_name='test',
            date=datetime.utcnow(),
            text='test'
        )

        SupervisionDocument.objects.create(
            domain=domain_name,
            document='test',
            data_type='test',
            name='test'
        )

    def setUp(self):
        self.domain = Domain(name="test", is_active=True)
        self.domain.save()
        self.domain2 = Domain(name="test2", is_active=True)
        self.domain2.save()
        self.locations = {}
        LocationType.objects.create(
            domain='test',
            name='facility',
        )
        LocationType.objects.create(
            domain='test2',
            name='facility',
        )

        self._create_data('test')
        self._create_data('test2')

    def test_pre_delete_signal_receiver(self):
        self.domain.delete()

        self.assertEqual(ProductAvailabilityData.objects.filter(location_id=self.locations['test']).count(), 0)
        self.assertEqual(ProductAvailabilityData.objects.filter(location_id=self.locations['test2']).count(), 1)

        self.assertEqual(OrganizationSummary.objects.filter(location_id=self.locations['test']).count(), 0)
        self.assertEqual(OrganizationSummary.objects.filter(location_id=self.locations['test2']).count(), 1)

        self.assertEqual(GroupSummary.objects.filter(org_summary__location_id=self.locations['test']).count(), 0)
        self.assertEqual(GroupSummary.objects.filter(org_summary__location_id=self.locations['test2']).count(), 1)

        self.assertEqual(Alert.objects.filter(location_id=self.locations['test']).count(), 0)
        self.assertEqual(Alert.objects.filter(location_id=self.locations['test2']).count(), 1)

        self.assertEqual(DeliveryGroupReport.objects.filter(location_id=self.locations['test']).count(), 0)
        self.assertEqual(DeliveryGroupReport.objects.filter(location_id=self.locations['test2']).count(), 1)

        self.assertEqual(SupplyPointWarehouseRecord.objects.filter(supply_point=self.locations['test']).count(), 0)
        self.assertEqual(SupplyPointWarehouseRecord.objects.filter(
            supply_point=self.locations['test2']
        ).count(), 1)

        self.assertEqual(SupplyPointStatus.objects.filter(location_id=self.locations['test']).count(), 0)
        self.assertEqual(SupplyPointStatus.objects.filter(location_id=self.locations['test2']).count(), 1)

        self.assertEqual(HistoricalLocationGroup.objects.filter(
            location_id__location_id=self.locations['test']
        ).count(), 0)
        self.assertEqual(HistoricalLocationGroup.objects.filter(
            location_id__location_id=self.locations['test2']
        ).count(), 1)

        self.assertEqual(ReportRun.objects.filter(domain='test').count(), 0)
        self.assertEqual(ReportRun.objects.filter(domain='test2').count(), 1)

        self.assertEqual(ILSNotes.objects.filter(domain='test').count(), 0)
        self.assertEqual(ILSNotes.objects.filter(domain='test2').count(), 1)

        self.assertEqual(SupervisionDocument.objects.filter(domain='test').count(), 0)
        self.assertEqual(SupervisionDocument.objects.filter(domain='test2').count(), 1)

    def tearDown(self):
        self.domain2.delete()
