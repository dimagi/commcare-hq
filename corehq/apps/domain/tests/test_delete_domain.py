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
        LocationType.objects.create(
            domain='test',
            name='facility2',
        )
        LocationType.objects.create(
            domain='test2',
            name='facility2',
        )
        for i in xrange(2):
            self._create_data('test', i)
            self._create_data('test2', i)

    def _assert_sql_counts(self, domain, number):
        self.assertEqual(StockTransaction.objects.filter(report__domain=domain).count(), number)
        self.assertEqual(StockReport.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLLocation.objects.filter(domain=domain).count(), number)
        self.assertEqual(SQLProduct.objects.filter(domain=domain).count(), number)
        self.assertEqual(DocDomainMapping.objects.filter(domain_name=domain).count(), number)
        self.assertEqual(LocationType.objects.filter(domain=domain).count(), number)

    def test_sql_objects_deletion(self):
        self._assert_sql_counts('test', 2)
        self.domain.delete()
        self._assert_sql_counts('test', 0)
        self._assert_sql_counts('test2', 2)

    def tearDown(self):
        self.domain2.delete()
