import random
import string
from xml.etree import ElementTree

from corehq.apps.app_manager.tests import XmlTest
from corehq.apps.commtrack.models import Product, product_fixture_generator
from corehq.apps.commtrack.tests import CommTrackTest
from corehq.apps.commtrack.tests.util import bootstrap_user


class FixtureTest(CommTrackTest, XmlTest):

    def _random_string(self, length):
        return ''.join(random.choice(string.ascii_lowercase)
                       for _ in range(length))

    def _initialize_product_names(self, count):
        product_names = sorted([self._random_string(20) for _ in range(count)])
        def get_product_name():
            for name in product_names:
                yield name
        self.product_names = get_product_name()

    def test_product_fixture(self):
        user = bootstrap_user(self, phone_number="1234567890")
        user_id = user.user_id
        products = ''
        product_list = Product.by_domain(user.domain)
        self._initialize_product_names(len(product_list))
        for product in product_list:
            product_id = product._id
            product_name  = self.product_names.next()
            product_unit = self._random_string(20)
            product_code = self._random_string(20)
            product_description = self._random_string(20)
            product_category = self._random_string(20)
            product_program_id = self._random_string(20)
            product_cost = float('%g' % random.uniform(1, 100))

            product_str = '<product id="%s">' % product_id
            product_str += '<name>%s</name>' % product_name
            product_str += '<unit>%s</unit>' % product_unit
            product_str += '<code>%s</code>' % product_code
            product_str += '<description>%s</description>' % product_description
            product_str += '<category>%s</category>' % product_category
            product_str += '<program_id>%s</program_id>' % product_program_id
            product_str += '<cost>%g</cost>' % product_cost
            product_str += '</product>'
            products += product_str

            product.name = product_name
            product.unit = product_unit
            product.code = product_code
            product.description = product_description
            product.category = product_category
            product.program_id = product_program_id
            product.cost = product_cost
            product.save()
        fixture = product_fixture_generator(user)
        self.assertXmlEqual(('<fixture id="commtrack:products" user_id="%s">'
                                + '<products>'
                                + products
                                + '</products>'
                                + '</fixture>') % user_id,
                            ElementTree.tostring(fixture[0]))
