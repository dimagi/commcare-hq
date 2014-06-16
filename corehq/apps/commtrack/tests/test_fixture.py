import random
import string
from xml.etree import ElementTree

from casexml.apps.case.xml import V1
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.commtrack.fixtures import product_fixture_generator, program_fixture_generator
from corehq.apps.commtrack.models import Product, Program
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.tests.util import bootstrap_user


class FixtureTest(CommTrackTest, TestFileMixin):

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
        for i, product in enumerate(product_list):
            product_id = product._id
            product_name = self.product_names.next()
            product_unit = self._random_string(20)
            product_code = self._random_string(20)
            product_description = self._random_string(20)
            product_category = self._random_string(20)
            product_program_id = self._random_string(20)
            product_cost = 0 if i == 0 else float('%g' % random.uniform(1, 100))

            # only set this on one product, so we can also test that
            # this node doesn't get sent down on every product
            if i == 0:
                product_data = {
                    'special_number': '555111'
                }

                custom_data_xml = '''
                    <product_data>
                        <special_number>555111</special_number>
                    </product_data>
                '''
            else:
                product_data = {}
                custom_data_xml = ''

            products += '''
                <product id="{id}">
                    <name>{name}</name>
                    <unit>{unit}</unit>
                    <code>{code}</code>
                    <description>{description}</description>
                    <category>{category}</category>
                    <program_id>{program_id}</program_id>
                    <cost>{cost}</cost>
                    {custom_data}
                </product>
            '''.format(
                id=product_id,
                name=product_name,
                unit=product_unit,
                code=product_code,
                description=product_description,
                category=product_category,
                program_id=product_program_id,
                cost=product_cost,
                custom_data=custom_data_xml
            )

            product.name = product_name
            product.unit = product_unit
            product.code = product_code
            product.description = product_description
            product.category = product_category
            product.program_id = product_program_id
            product.cost = product_cost
            product.product_data = product_data
            product.save()
        fixture = product_fixture_generator(user, V1, None)

        self.assertXmlEqual('''<fixture id="commtrack:products" user_id="{user_id}">
                                    <products>
                                        {products}
                                    </products>
                                </fixture>'''.format(user_id=user_id, products=products),
                            ElementTree.tostring(fixture[0]))

    def test_program_fixture(self):
        user = bootstrap_user(self, phone_number="1234567890")
        Program(
            domain=user.domain,
            name="test1",
            code="t1"
        ).save()

        program_list = Program.by_domain(user.domain)
        program_xml = ''
        for program in program_list:
            program_xml += '''
                <program id="{id}">
                    <name>{name}</name>
                    <code>{code}</code>
                </program>
            '''.format(
                id=program.get_id,
                name=program.name,
                code=program.code
            )

        fixture = program_fixture_generator(user, V1, None)

        self.assertXmlEqual('''<fixture id="commtrack:programs" user_id="{user_id}">
                                    <programs>
                                        {programs}
                                    </programs>
                                </fixture>'''.format(user_id=user.user_id, programs=program_xml),
                            ElementTree.tostring(fixture[0]))
