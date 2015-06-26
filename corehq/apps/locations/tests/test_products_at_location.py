from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.products.models import SQLProduct

from ..models import Location, LocationType


class ProductsAtLocationTest(TestCase):

    def assertEqualProducts(self, products1, products2):
        self.assertEquals(
            sorted(p.product_id for p in products1),
            sorted(p.product_id for p in products2),
        )

    def setUp(self):
        self.domain = bootstrap_domain()
        self.products = SQLProduct.objects.filter(domain=self.domain)
        LocationType(domain=self.domain.name, name='type').save()

    def test_add_products(self):
        couch_location = Location(
            name="Camelot",
            domain=self.domain.name,
            location_type="type",
        )
        couch_location.save()
        location = couch_location.sql_location
        location.products = self.products
        location.save()
        self.assertEqualProducts(couch_location.sql_location.products.all(),
                                 self.products)
