from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain
from corehq.apps.products.models import SQLProduct

from ..models import make_location, LocationType


class ProductsAtLocationTest(TestCase):

    domain = 'test-products-at-location'

    def assertEqualProducts(self, products1, products2):
        self.assertEquals(
            sorted(p.product_id for p in products1),
            sorted(p.product_id for p in products2),
        )

    def setUp(self):
        self.project = bootstrap_domain(self.domain)
        self.products = SQLProduct.objects.filter(domain=self.domain)
        LocationType(domain=self.domain, name='type').save()

    def tearDown(self):
        self.project.delete()

    def test_add_products(self):
        location = make_location(
            name="Camelot",
            domain=self.domain,
            location_type="type",
        )
        location.save()

        location.products = self.products
        location.save()
        self.assertEqualProducts(location.products.all(),
                                 self.products)
