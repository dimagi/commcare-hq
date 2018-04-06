from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase, TestCase
from corehq.apps.groups.tests.test_groups import WrapGroupTestMixin
from corehq.apps.products.models import Product, SQLProduct


class WrapProductTest(WrapGroupTestMixin, SimpleTestCase):
    document_class = Product


class TestActiveProductManager(TestCase):

    def test_active_objects(self):
        domain = 'test'
        p1 = SQLProduct.objects.create(domain=domain, product_id='test1', name='test1')
        p2 = SQLProduct.objects.create(domain=domain, product_id='test2', name='test2')
        parchived = SQLProduct.objects.create(domain=domain, product_id='test3', name='test3', is_archived=True)
        self.addCleanup(SQLProduct.objects.all().delete)
        self.assertEqual(2, SQLProduct.active_objects.count())
        self.assertEqual(2, SQLProduct.active_objects.filter(domain=domain).count())
        all_active = SQLProduct.active_objects.all()
        self.assertTrue(p1 in all_active)
        self.assertTrue(p2 in all_active)
        self.assertTrue(parchived not in all_active)
