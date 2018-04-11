from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_products, bootstrap_domain, make_product
from corehq.apps.products.models import Product, SQLProduct


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
        products = sorted(Product.by_domain(self.domain), key=lambda p: p._id)
        original_list = Product.by_domain(self.domain, wrap=False)

        products[0].archive()

        new_list = Product.by_domain(self.domain, wrap=False)

        self.assertTrue(
            products[0]._id not in [p['_id'] for p in new_list],
            "Archived product still returned by Product.by_domain()"
        )

        self.assertEqual(
            len(new_list),
            len(original_list) - 1
        )

        self.assertEqual(
            len(Product.by_domain(self.domain, wrap=False, include_archived=True)),
            len(original_list)
        )

        self.assertEqual(
            SQLProduct.objects.filter(domain=self.domain, is_archived=True).count(),
            1
        )

        products[0].unarchive()

        self.assertEqual(
            len(original_list),
            len(Product.by_domain(self.domain, wrap=False))
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
