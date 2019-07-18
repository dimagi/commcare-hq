from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
import random
import string
from xml.etree import cElementTree as ElementTree

from django.test import TestCase

from casexml.apps.phone.models import SyncLogSQL, properly_wrap_sync_log
from casexml.apps.phone.tests.utils import (
    call_fixture_generator,
    create_restore_user,
    deprecated_generate_restore_payload,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.programs.fixtures import program_fixture_generator
from corehq.apps.products.fixtures import product_fixture_generator
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
from corehq.apps.commtrack.tests import util
from six.moves import range


class FixtureTest(TestCase, TestXmlMixin):
    domain = "fixture-test"

    @classmethod
    def setUpClass(cls):
        super(FixtureTest, cls).setUpClass()
        cls.domain_obj = util.bootstrap_domain(cls.domain)
        util.bootstrap_location_types(cls.domain)
        util.bootstrap_products(cls.domain)
        cls.user = create_restore_user(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(FixtureTest, cls).tearDownClass()

    def _random_string(self, length):
        return ''.join(random.choice(string.ascii_lowercase)
                       for _ in range(length))

    def _initialize_product_names(self, count):
        product_names = sorted([self._random_string(20) for _ in range(count)])

        def get_product_name():
            for name in product_names:
                yield name
        self.product_names = get_product_name()

    def generate_product_xml(self, user, randomize_data=True):
        products = []
        product_list = Product.by_domain(user.domain)
        self._initialize_product_names(len(product_list))
        for i, product in enumerate(product_list):
            product_id = product._id
            product_name = next(self.product_names)
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

            product_xml = '''
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

            products.append((product, product_xml))

        products.sort(key=lambda p: p[0].code)
        return ''.join(product_xml for product, product_xml in products)

    def generate_product_fixture_xml(self, user, randomize_data=True):
        return """
            <fixture id="commtrack:products" indexed="true" user_id="{user_id}">
                <products>
                    {products}
                </products>
            </fixture>
        """.format(
            user_id=user.user_id,
            products=self.generate_product_xml(user, randomize_data)
        )

    def test_product_fixture(self):
        user = self.user
        fixture_xml = self.generate_product_fixture_xml(user)
        index_schema, fixture = call_fixture_generator(product_fixture_generator, user)

        self.assertXmlEqual(fixture_xml, fixture)

        schema_xml = """
            <schema id="commtrack:products">
                <indices>
                    <index>@id</index>
                    <index>category</index>
                    <index>code</index>
                    <index>program_id</index>
                </indices>
            </schema>
        """
        self.assertXmlEqual(schema_xml, ElementTree.tostring(index_schema))

        # test restore with different user
        user2 = create_restore_user(self.domain, username='user2')
        self.addCleanup(user2._couch_user.delete)
        fixture_xml = self.generate_product_fixture_xml(user2)
        index_schema, fixture = call_fixture_generator(product_fixture_generator, user2)

        self.assertXmlEqual(fixture_xml, fixture)

    def test_product_fixture_cache(self):
        user = self.user

        expected_xml = self.generate_product_fixture_xml(user)

        fixture_original = call_fixture_generator(product_fixture_generator, user)[1]
        self.assertXmlEqual(
            expected_xml,
            fixture_original
        )

        product = Product.by_domain(user.domain)[0]
        product.name = 'new_name'
        super(Product, product).save()  # save but skip clearing the cache

        fixture_cached = call_fixture_generator(product_fixture_generator, user)[1]
        self.assertXmlEqual(
            expected_xml,
            fixture_cached
        )

        # This will update all the products and re-save them.
        expected_xml_new = self.generate_product_fixture_xml(user)

        fixture_cached = call_fixture_generator(product_fixture_generator, user)[1]
        self.assertXmlEqual(
            expected_xml_new,
            fixture_cached
        )
        self.assertXMLNotEqual(expected_xml_new, expected_xml)

    def generate_program_xml(self, program_list, user):
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

        return """
            <fixture id="commtrack:programs" user_id="{user_id}">
                <programs>
                    {programs}
                </programs>
            </fixture>
        """.format(
            user_id=user.user_id,
            programs=program_xml
        )

    def _get_latest_synclog(self):
        return properly_wrap_sync_log(SyncLogSQL.objects.order_by('date').last().doc)

    def test_program_fixture(self):
        user = self.user
        Program(
            domain=user.domain,
            name="test1",
            code="t1"
        ).save()

        program_list = Program.by_domain(user.domain)
        program_xml = self.generate_program_xml(program_list, user)

        fixture = call_fixture_generator(program_fixture_generator, user)

        self.assertXmlEqual(
            program_xml,
            fixture[0]
        )

        # test restore with different user
        user2 = create_restore_user(self.domain, username='user2')
        self.addCleanup(user2._couch_user.delete)
        program_xml = self.generate_program_xml(program_list, user2)
        fixture = call_fixture_generator(program_fixture_generator, user2)

        self.assertXmlEqual(
            program_xml,
            fixture[0]
        )

    def test_program_fixture_cache(self):
        user = self.user
        Program(
            domain=user.domain,
            name="test1",
            code="t1"
        ).save()

        program_list = list(Program.by_domain(user.domain))
        program_xml = self.generate_program_xml(program_list, user)

        fixture = call_fixture_generator(program_fixture_generator, user)

        self.assertXmlEqual(
            program_xml,
            fixture[0]
        )

        program = program_list[0]
        program.name = 'new_name'
        super(Program, program).save()  # save but skip clearing the cache

        fixture_cached = call_fixture_generator(program_fixture_generator, user)
        self.assertXmlEqual(
            program_xml,
            fixture_cached[0]
        )

        program.save()
        program_xml_new = self.generate_program_xml(program_list, user)

        fixture_regen = call_fixture_generator(program_fixture_generator, user)
        self.assertXmlEqual(
            program_xml_new,
            fixture_regen[0]
        )
        self.assertXMLNotEqual(program_xml_new, program_xml)
