from django.test import TestCase

from corehq.apps.commtrack.tests.util import (
    bootstrap_domain,
    bootstrap_products,
    make_product,
)
from corehq.apps.products.models import SQLProduct


class ProductsTest(TestCase):
    domain = 'products-test'

    @classmethod
    def setUpClass(cls):
        super(ProductsTest, cls).setUpClass()
        cls.domain_obj = bootstrap_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(ProductsTest, cls).tearDownClass()

    def test_archive(self):
        bootstrap_products(self.domain)
        products = SQLProduct.active_objects.filter(domain=self.domain).order_by('product_id')
        original_number_products = SQLProduct.active_objects.filter(domain=self.domain).count()

        products[0].archive()

        new_list = SQLProduct.active_objects.filter(domain=self.domain).values_list('product_id', flat=True)

        self.assertTrue(
            products[0].product_id not in new_list,
            "Archived product still returned by active_objects"
        )

        self.assertEqual(len(new_list), original_number_products - 1)

        self.assertEqual(
            SQLProduct.objects.filter(domain=self.domain).count(),
            original_number_products
        )

        self.assertEqual(
            SQLProduct.objects.filter(domain=self.domain, is_archived=True).count(),
            1
        )

        products[0].unarchive()

        self.assertEqual(
            original_number_products,
            SQLProduct.active_objects.filter(domain=self.domain).count(),
        )

    def test_sync(self):
        product = make_product(self.domain, 'Sample Product 3', 'pr', '')

        product.name = "new_name"
        product.domain = "new_domain"
        product.save()

        try:
            sql_product = SQLProduct.objects.get(
                name="new_name",
                domain="new_domain",
            )

            self.assertEqual(sql_product.name, "new_name")
            self.assertEqual(sql_product.domain, "new_domain")
        except SQLProduct.DoesNotExist:
            self.fail("Synced SQL object does not exist")
