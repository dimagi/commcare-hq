from decimal import Decimal
from django.test import TestCase

from corehq.apps.consumption.const import DAYS_IN_MONTH
from corehq.apps.consumption.shortcuts import (
    get_default_monthly_consumption,
    set_default_consumption_for_product,
    set_default_monthly_consumption_for_domain,
)

from .models import (
    TYPE_DOMAIN,
    TYPE_PRODUCT,
    TYPE_SUPPLY_POINT,
    TYPE_SUPPLY_POINT_TYPE,
    DefaultConsumption,
)

domain = 'consumption-test'
product_id = 'test-product'
type_id = 'facilities'
supply_point_id = 'test-facility'


class ConsumptionTestBase(TestCase):

    def setUp(self):
        _delete_all_consumptions()
        self.assertEqual(0, _count_consumptions())

    def tearDown(self):
        _delete_all_consumptions()
        self.assertEqual(0, _count_consumptions())


class GetDefaultConsumptionTestCase(ConsumptionTestBase):

    def get_default_consumption(self, domain, product_id, location_type, case_id):
        consumption = get_default_monthly_consumption(domain, product_id, location_type, case_id)

        if consumption:
            return consumption / Decimal(DAYS_IN_MONTH)
        else:
            return None

    def testGetNoDefault(self):
        self.assertEqual(None, self.get_default_consumption(domain, 'whatever', 'goes', 'here'))

    def testGetDomainOnly(self):
        _create_domain_consumption(5)
        self.assertEqual(5, self.get_default_consumption(domain, 'whatever', 'goes', 'here'))
        self.assertEqual(None, self.get_default_consumption('wrong', 'whatever', 'goes', 'here'))

    def testGetForProduct(self):
        _create_product_consumption(5)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, 'doesnt', 'matter'))
        self.assertEqual(None, self.get_default_consumption(domain, 'wrong', 'doesnt', 'matter'))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, 'doesnt', 'matter'))

        _create_domain_consumption(3)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, 'doesnt', 'matter'))
        self.assertEqual(3, self.get_default_consumption(domain, 'wrong', 'doesnt', 'matter'))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, 'doesnt', 'matter'))

    def testGetForType(self):
        _create_type_consumption(5)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, 'useless'))
        self.assertEqual(None, self.get_default_consumption(domain, product_id, 'wrong', 'useless'))
        self.assertEqual(None, self.get_default_consumption(domain, 'wrong', type_id, 'useless'))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, 'useless'))

        _create_product_consumption(3)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, 'useless'))
        self.assertEqual(3, self.get_default_consumption(domain, product_id, 'wrong', 'useless'))
        self.assertEqual(None, self.get_default_consumption(domain, 'wrong', type_id, 'useless'))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, 'useless'))

        _create_domain_consumption(2)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, 'useless'))
        self.assertEqual(3, self.get_default_consumption(domain, product_id, 'wrong', 'useless'))
        self.assertEqual(2, self.get_default_consumption(domain, 'wrong', type_id, 'useless'))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, 'useless'))

    def testGetForId(self):
        _create_id_consumption(5)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, self.get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(None, self.get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(None, self.get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(None, self.get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, supply_point_id))

        _create_type_consumption(4)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, self.get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(4, self.get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(None, self.get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(None, self.get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, supply_point_id))

        _create_product_consumption(3)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, self.get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(4, self.get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(3, self.get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(None, self.get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, supply_point_id))

        _create_domain_consumption(2)
        self.assertEqual(5, self.get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, self.get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(4, self.get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(3, self.get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(2, self.get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, self.get_default_consumption('wrong', product_id, type_id, supply_point_id))


class ConsumptionShortcutsTestCase(ConsumptionTestBase):

    def testSetForDomain(self):
        self.assertEqual(None, DefaultConsumption.get_domain_default(domain))
        default = set_default_monthly_consumption_for_domain(domain, 50)
        self.assertEqual(50, DefaultConsumption.get_domain_default(domain).default_consumption)
        self.assertEqual(1, _count_consumptions())
        updated = set_default_monthly_consumption_for_domain(domain, 40)
        self.assertEqual(default.id, updated.id)
        self.assertEqual(40, DefaultConsumption.get_domain_default(domain).default_consumption)
        self.assertEqual(1, _count_consumptions())

    def testSetForProduct(self):
        self.assertEqual(None, DefaultConsumption.get_product_default(domain, product_id))
        default = set_default_consumption_for_product(domain, product_id, 50)
        self.assertEqual(50, DefaultConsumption.get_product_default(domain, product_id).default_consumption)
        self.assertEqual(1, _count_consumptions())
        updated = set_default_consumption_for_product(domain, product_id, 40)
        self.assertEqual(default.id, updated.id)
        self.assertEqual(40, DefaultConsumption.get_product_default(domain, product_id).default_consumption)
        self.assertEqual(1, _count_consumptions())


def _create_domain_consumption(amt, domain=domain):
    DefaultConsumption(domain=domain, default_consumption=amt * DAYS_IN_MONTH, type=TYPE_DOMAIN).save()


def _create_product_consumption(amt, domain=domain, product_id=product_id):
    DefaultConsumption(
        domain=domain,
        default_consumption=amt * DAYS_IN_MONTH,
        type=TYPE_PRODUCT,
        product_id=product_id
    ).save()


def _create_type_consumption(amt, domain=domain, product_id=product_id, type_id=type_id):
    DefaultConsumption(
        domain=domain,
        default_consumption=amt * DAYS_IN_MONTH,
        type=TYPE_SUPPLY_POINT_TYPE,
        product_id=product_id,
        supply_point_type=type_id
    ).save()


def _create_id_consumption(amt, domain=domain, product_id=product_id, supply_point_id=supply_point_id):
    DefaultConsumption(
        domain=domain,
        default_consumption=amt * DAYS_IN_MONTH,
        type=TYPE_SUPPLY_POINT,
        product_id=product_id,
        supply_point_id=supply_point_id
    ).save()


def _count_consumptions():
    return DefaultConsumption.objects.count()


def _delete_all_consumptions():
    DefaultConsumption.objects.all().delete()
