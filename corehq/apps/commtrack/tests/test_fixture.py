import random
import string
from xml.etree import ElementTree

from casexml.apps.case.xml import V1
from casexml.apps.phone.tests.utils import generate_restore_payload
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.programs.fixtures import program_fixture_generator
from corehq.apps.products.fixtures import product_fixture_generator
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.tests.util import bootstrap_user
from casexml.apps.phone.models import SyncLog
import datetime


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

    def generate_product_xml(self, user, randomize_data=True):
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

        return products

    def generate_product_fixture_xml(self, user, randomize_data=True):
        return """
            <fixture id="commtrack:products" user_id="{user_id}">
                <products>
                    {products}
                </products>
            </fixture>
        """.format(
            user_id=user.user_id,
            products=self.generate_product_xml(user, randomize_data)
        )

    def test_product_fixture(self):
        user = bootstrap_user(self, phone_number="1234567890")
        xml = self.generate_product_fixture_xml(user)
        fixture = product_fixture_generator(user, V1)

        self.assertXmlEqual(
            xml,
            ElementTree.tostring(fixture[0])
        )

    def test_selective_product_sync(self):
        user = bootstrap_user(self, phone_number="1234567890")

        expected_xml = self.generate_product_fixture_xml(user)

        product_list = Product.by_domain(user.domain)
        self._initialize_product_names(len(product_list))

        fixture_original = product_fixture_generator(user, V1)
        generate_restore_payload(self.domain, user.to_casexml_user())
        self.assertXmlEqual(
            expected_xml,
            ElementTree.tostring(fixture_original[0])
        )

        first_sync = sorted(SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False
        ).all(), key=lambda x: x.date)[-1]

        # make sure the time stamp on this first sync is
        # not on the same second that the products were created
        first_sync.date += datetime.timedelta(seconds=1)

        # second sync is before any changes are made, so there should
        # be no products synced
        fixture_pre_change = product_fixture_generator(user, V1, last_sync=first_sync)
        generate_restore_payload(self.domain, user.to_casexml_user())
        self.assertEqual(
            [],
            fixture_pre_change,
            "Fixture was not empty on second sync"
        )

        second_sync = sorted(SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False
        ).all(), key=lambda x: x.date)[-1]

        self.assertTrue(first_sync._id != second_sync._id)

        # save should make the product more recently updated than the
        # last sync
        for product in product_list:
            product.save()

        # now that we've updated a product, we should get
        # product data in sync again
        fixture_post_change = product_fixture_generator(user, V1, last_sync=second_sync)

        # regenerate the fixture xml to make sure it is still legit
        self.assertXmlEqual(
            expected_xml,
            ElementTree.tostring(fixture_post_change[0])
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

    def test_program_fixture(self):
        user = bootstrap_user(self, phone_number="1234567890")
        Program(
            domain=user.domain,
            name="test1",
            code="t1"
        ).save()

        program_list = Program.by_domain(user.domain)
        program_xml = self.generate_program_xml(program_list, user)

        fixture = program_fixture_generator(user, V1)

        self.assertXmlEqual(
            program_xml,
            ElementTree.tostring(fixture[0])
        )

    def test_selective_program_sync(self):
        user = bootstrap_user(self, phone_number="1234567890")
        Program(
            domain=user.domain,
            name="test1",
            code="t1"
        ).save()

        program_list = Program.by_domain(user.domain)
        program_xml = self.generate_program_xml(program_list, user)

        fixture_original = program_fixture_generator(user, V1)

        generate_restore_payload(self.domain, user.to_casexml_user())
        self.assertXmlEqual(
            program_xml,
            ElementTree.tostring(fixture_original[0])
        )

        first_sync = sorted(SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False
        ).all(), key=lambda x: x.date)[-1]

        # make sure the time stamp on this first sync is
        # not on the same second that the programs were created
        first_sync.date += datetime.timedelta(seconds=1)

        # second sync is before any changes are made, so there should
        # be no programs synced
        fixture_pre_change = program_fixture_generator(user, V1, last_sync=first_sync)
        generate_restore_payload(self.domain, user.to_casexml_user())
        self.assertEqual(
            [],
            fixture_pre_change,
            "Fixture was not empty on second sync"
        )

        second_sync = sorted(SyncLog.view(
            "phone/sync_logs_by_user",
            include_docs=True,
            reduce=False
        ).all(), key=lambda x: x.date)[-1]

        self.assertTrue(first_sync._id != second_sync._id)

        # save should make the program more recently updated than the
        # last sync
        for program in program_list:
            program.save()

        # now that we've updated a program, we should get
        # program data in sync again
        fixture_post_change = program_fixture_generator(user, V1, last_sync=second_sync)

        # regenerate the fixture xml to make sure it is still legit
        self.assertXmlEqual(
            program_xml,
            ElementTree.tostring(fixture_post_change[0])
        )
