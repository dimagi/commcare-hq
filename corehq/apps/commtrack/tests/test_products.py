from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.models import Product, DbProduct


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
            len(original_list) - 1,
            len(new_list)
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
            db_product = DbProduct.objects.get(
                name="new_name",
                domain="new_domain",
            )

            self.assertEqual(db_product.name, "new_name")
            self.assertEqual(db_product.domain, "new_domain")
        except DbProduct.DoesNotExist:
            self.fail("Synced SQL object does not exist")
