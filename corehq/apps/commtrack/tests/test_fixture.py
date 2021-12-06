import datetime
import doctest
import random
import string
from contextlib import contextmanager
from xml.etree import cElementTree as ElementTree
from xml.etree.ElementTree import tostring

from django.test import TestCase

import attr

from casexml.apps.phone.models import SyncLogSQL, properly_wrap_sync_log
from casexml.apps.phone.tests.utils import (
    call_fixture_generator,
    create_restore_user,
    deprecated_generate_restore_payload,
)

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.commtrack.fixtures import simple_fixture_generator
from corehq.apps.commtrack.tests import util
from corehq.apps.products.fixtures import product_fixture_generator
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.programs.fixtures import program_fixture_generator
from corehq.apps.programs.models import Program


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

        self.assertXmlEqual(fixture_xml, ElementTree.tostring(fixture, encoding='utf-8'))

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
        self.assertXmlEqual(schema_xml, ElementTree.tostring(index_schema, encoding='utf-8'))

        # test restore with different user
        user2 = create_restore_user(self.domain, username='user2')
        self.addCleanup(user2._couch_user.delete, self.domain, deleted_by=None)
        fixture_xml = self.generate_product_fixture_xml(user2)
        index_schema, fixture = call_fixture_generator(product_fixture_generator, user2)

        self.assertXmlEqual(fixture_xml, ElementTree.tostring(fixture, encoding='utf-8'))

    def test_selective_product_sync(self):
        user = self.user

        expected_xml = self.generate_product_fixture_xml(user)

        product_list = Product.by_domain(user.domain)
        self._initialize_product_names(len(product_list))

        fixture_original = call_fixture_generator(product_fixture_generator, user)[1]
        deprecated_generate_restore_payload(self.domain_obj, user)
        self.assertXmlEqual(
            expected_xml,
            ElementTree.tostring(fixture_original, encoding='utf-8')
        )

        first_sync = self._get_latest_synclog()

        # make sure the time stamp on this first sync is
        # not on the same second that the products were created
        first_sync.date += datetime.timedelta(seconds=1)

        # second sync is before any changes are made, so there should
        # be no products synced
        fixture_pre_change = call_fixture_generator(product_fixture_generator, user, last_sync=first_sync)
        deprecated_generate_restore_payload(self.domain_obj, user)
        self.assertEqual(
            [],
            fixture_pre_change,
            "Fixture was not empty on second sync"
        )

        second_sync = self._get_latest_synclog()

        self.assertTrue(first_sync._id != second_sync._id)

        # save should make the product more recently updated than the
        # last sync
        for product in product_list:
            product.save()

        # now that we've updated a product, we should get
        # product data in sync again
        fixture_post_change = call_fixture_generator(product_fixture_generator, user, last_sync=second_sync)[1]

        # regenerate the fixture xml to make sure it is still legit
        self.assertXmlEqual(
            expected_xml,
            ElementTree.tostring(fixture_post_change, encoding='utf-8')
        )

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
            ElementTree.tostring(fixture[0], encoding='utf-8')
        )

        # test restore with different user
        user2 = create_restore_user(self.domain, username='user2')
        self.addCleanup(user2._couch_user.delete, self.domain, deleted_by=None)
        program_xml = self.generate_program_xml(program_list, user2)
        fixture = call_fixture_generator(program_fixture_generator, user2)

        self.assertXmlEqual(
            program_xml,
            ElementTree.tostring(fixture[0], encoding='utf-8')
        )

    def test_selective_program_sync(self):
        user = self.user
        Program(
            domain=user.domain,
            name="test1",
            code="t1"
        ).save()

        program_list = Program.by_domain(user.domain)
        program_xml = self.generate_program_xml(program_list, user)

        fixture_original = call_fixture_generator(program_fixture_generator, user)

        deprecated_generate_restore_payload(self.domain_obj, user)
        self.assertXmlEqual(
            program_xml,
            ElementTree.tostring(fixture_original[0], encoding='utf-8')
        )

        first_sync = self._get_latest_synclog()
        # make sure the time stamp on this first sync is
        # not on the same second that the programs were created
        first_sync.date += datetime.timedelta(seconds=1)

        # second sync is before any changes are made, so there should
        # be no programs synced
        fixture_pre_change = call_fixture_generator(program_fixture_generator, user, last_sync=first_sync)
        deprecated_generate_restore_payload(self.domain_obj, user)
        self.assertEqual(
            [],
            fixture_pre_change,
            "Fixture was not empty on second sync"
        )

        second_sync = self._get_latest_synclog()

        self.assertTrue(first_sync._id != second_sync._id)

        # save should make the program more recently updated than the
        # last sync
        for program in program_list:
            program.save()

        # now that we've updated a program, we should get
        # program data in sync again
        fixture_post_change = call_fixture_generator(program_fixture_generator, user, last_sync=second_sync)

        # regenerate the fixture xml to make sure it is still legit
        self.assertXmlEqual(
            program_xml,
            ElementTree.tostring(fixture_post_change[0], encoding='utf-8')
        )


@attr.s(auto_attribs=True)
class MockUser:
    user_id: str


class SimpleFixtureGeneratorTests(TestCase):

    def test_product_decimal_value(self):
        products = [
            Product(
                _id="1",
                domain="test-domain",
                name="Foo",
                code_="foo",
                cost=10,
            ),
            Product(
                _id="2",
                domain="test-domain",
                name="Bar",
                code_="bar",
                cost=9.99,
            ),
            Product(
                _id="3",
                domain="test-domain",
                name="Baz",
                code_="baz",
                cost=10.0,
            ),
        ]
        fixtures = simple_fixture_generator(
            restore_user=MockUser(user_id="123456"),
            id="7890ab",
            name="test-fixture",
            fields=("name", "code", "cost"),
            data=products,
        )
        xml = tostring(fixtures[0])
        self.assertEqual(xml, self.get_expected_xml())

    def test_sqlproduct_decimal_value(self):
        with get_sql_products() as products:
            fixtures = simple_fixture_generator(
                restore_user=MockUser(user_id="123456"),
                id="7890ab",
                name="test-fixture",
                fields=("name", "code", "cost"),
                data=products,
            )
        xml = tostring(fixtures[0])
        self.assertEqual(xml, self.get_expected_xml())

    @staticmethod
    def get_expected_xml():
        _expected_xml = b"""
            <fixture id="7890ab" user_id="123456">
                <test-fixtures>
                    <test-fixture id="1">
                        <name>Foo</name>
                        <code>foo</code>
                        <cost>10</cost>
                    </test-fixture>
                    <test-fixture id="2">
                        <name>Bar</name>
                        <code>bar</code>
                        <cost>9.99</cost>
                    </test-fixture>
                    <test-fixture id="3">
                        <name>Baz</name>
                        <code>baz</code>
                        <cost>10</cost>
                    </test-fixture>
                </test-fixtures>
            </fixture>"""
        return b"".join([line.strip() for line in _expected_xml.split(b"\n")])


@contextmanager
def get_sql_products():
    products = [
        SQLProduct.objects.create(
            product_id="1",
            domain="test-domain",
            name="Foo",
            code="foo",
            cost=10,
        ),
        SQLProduct.objects.create(
            product_id="2",
            domain="test-domain",
            name="Bar",
            code="bar",
            cost=9.99,
        ),
        SQLProduct.objects.create(
            product_id="3",
            domain="test-domain",
            name="Baz",
            code="baz",
            cost=10.0,
        ),
    ]
    try:
        # We have to save and fetch them to ensure that ``cost`` is cast as Decimal
        yield SQLProduct.objects.filter(domain="test-domain").order_by("product_id")
    finally:
        for p in products:
            p.delete()


def test_doctests():
    import corehq.apps.commtrack.fixtures
    results = doctest.testmod(corehq.apps.commtrack.fixtures)
    assert results.failed == 0
