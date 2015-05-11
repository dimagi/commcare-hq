from corehq.apps.groups.tests import WrapGroupTest
from corehq.apps.products.models import Product


class WrapProductTest(WrapGroupTest):
    document_class = Product
