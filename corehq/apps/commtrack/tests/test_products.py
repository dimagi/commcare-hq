from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.products.models import Product, SQLProduct


class ProductsTest(CommTrackTest):
    def test_archive(self):
        original_list = Product.by_domain(self.domain.name, wrap=False)

        self.products[0].archive()

        new_list = Product.by_domain(self.domain.name, wrap=False)

        self.assertTrue(
            self.products[0]._id not in [p['_id'] for p in new_list],
            "Archived product still returned by Product.by_domain()"
        )

        self.assertEqual(
            len(new_list),
            len(original_list) - 1
        )

        self.assertEqual(
            len(Product.by_domain(self.domain.name, wrap=False, include_archived=True)),
            len(original_list)
        )

        self.assertEqual(
            SQLProduct.objects.filter(domain=self.domain.name, is_archived=True).count(),
            1
        )

        self.products[0].unarchive()

        self.assertEqual(
            len(original_list),
            len(Product.by_domain(self.domain.name, wrap=False))
        )

    def test_sync(self):
        product = self.products[1]

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
