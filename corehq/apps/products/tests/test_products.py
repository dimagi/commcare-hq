from django.test import SimpleTestCase
from corehq.apps.groups.tests import WrapGroupTestMixin
from corehq.apps.products.models import Product


class WrapProductTest(WrapGroupTestMixin, SimpleTestCase):
    document_class = Product
