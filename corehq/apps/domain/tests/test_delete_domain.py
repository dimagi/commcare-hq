from datetime import datetime
from django.test import TestCase
from casexml.apps.stock.models import DocDomainMapping, StockReport, StockTransaction
from corehq import Domain
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location, LocationType, SQLLocation
from corehq.apps.products.models import Product, SQLProduct


class TestDeleteDomain(TestCase):

    def _create_data(self, domain_name, i):
        product = Product(domain=domain_name, name='test-{}'.format(i))
        product.save()

        location = Location(
            domain=domain_name,
            site_code='testcode-{}'.format(i),
            name='test-{}'.format(i),
            location_type='facility'
        )
        location.save()
        SupplyPointCase.create_from_location(domain_name, location)
        report = StockReport.objects.create(
            type='balance',
            domain=domain_name,
            form_id='fake',
            date=datetime.utcnow()
        )

        StockTransaction.objects.create(
            report=report,
            product_id=product.get_id,
            sql_product=SQLProduct.objects.get(product_id=product.get_id),
            section_id='stock',
            type='stockonhand',
            case_id=location.linked_supply_point().get_id,
            stock_on_hand=100
        )

    def setUp(self):
        self.domain = Domain(name="test", is_active=True)
        self.domain.save()
        self.domain2 = Domain(name="test2", is_active=True)
        self.domain2.save()
        LocationType.objects.create(
            domain='test',
            name='facility',
        )
        LocationType.objects.create(
            domain='test2',
            name='facility',
        )
        for i in xrange(2):
            self._create_data('test', i)
            self._create_data('test2', i)

    def test_sql_objects_deletion(self):
        self.domain.delete()
        self.assertEqual(StockTransaction.objects.filter(report__domain='test').count(), 0)
        self.assertEqual(StockReport.objects.filter(domain='test').count(), 0)
        self.assertEqual(SQLLocation.objects.filter(domain='test').count(), 0)
        self.assertEqual(SQLProduct.objects.filter(domain='test').count(), 0)
        self.assertEqual(LocationType.objects.filter(domain='test').count(), 0)
        self.assertEqual(DocDomainMapping.objects.filter(domain_name='test').count(), 0)

        self.assertEqual(StockTransaction.objects.filter(report__domain='test2').count(), 2)
        self.assertEqual(StockReport.objects.filter(domain='test2').count(), 2)
        self.assertEqual(SQLLocation.objects.filter(domain='test2').count(), 2)
        self.assertEqual(SQLProduct.objects.filter(domain='test2').count(), 2)
        self.assertEqual(LocationType.objects.filter(domain='test2').count(), 1)
        self.assertEqual(DocDomainMapping.objects.filter(domain_name='test2').count(), 2)

    def tearDown(self):
        self.domain2.delete()
