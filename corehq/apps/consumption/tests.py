from django.test import TestCase
from corehq.apps.consumption.shortcuts import get_default_consumption
from .models import DefaultConsumption, TYPE_DOMAIN, TYPE_PRODUCT, TYPE_SUPPLY_POINT_TYPE, TYPE_SUPPLY_POINT

domain = 'consumption-test'
product_id = 'test-product'
type_id = 'facilities'
supply_point_id = 'test-facility'

class DefaultConsumptionTestCase(TestCase):

    def tearDown(self):
        for consumption in DefaultConsumption.view('consumption/consumption_index',
                                                   reduce=False, include_docs=True):
            consumption.delete()

    def testGetNoDefault(self):
        self.assertEqual(None, get_default_consumption(domain, 'whatever', 'goes', 'here'))

    def testGetDomainOnly(self):
        _create_domain_consumption(5)
        self.assertEqual(5, get_default_consumption(domain, 'whatever', 'goes', 'here'))
        self.assertEqual(None, get_default_consumption('wrong', 'whatever', 'goes', 'here'))

    def testGetForProduct(self):
        _create_product_consumption(5)
        self.assertEqual(5, get_default_consumption(domain, product_id, 'doesnt', 'matter'))
        self.assertEqual(None, get_default_consumption(domain, 'wrong', 'doesnt', 'matter'))
        self.assertEqual(None, get_default_consumption('wrong', product_id, 'doesnt', 'matter'))

        _create_domain_consumption(3)
        self.assertEqual(5, get_default_consumption(domain, product_id, 'doesnt', 'matter'))
        self.assertEqual(3, get_default_consumption(domain, 'wrong', 'doesnt', 'matter'))
        self.assertEqual(None, get_default_consumption('wrong', product_id, 'doesnt', 'matter'))

    def testGetForType(self):
        _create_type_consumption(5)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, 'useless'))
        self.assertEqual(None, get_default_consumption(domain, product_id, 'wrong', 'useless'))
        self.assertEqual(None, get_default_consumption(domain, 'wrong', type_id, 'useless'))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, 'useless'))

        _create_product_consumption(3)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, 'useless'))
        self.assertEqual(3, get_default_consumption(domain, product_id, 'wrong', 'useless'))
        self.assertEqual(None, get_default_consumption(domain, 'wrong', type_id, 'useless'))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, 'useless'))

        _create_domain_consumption(2)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, 'useless'))
        self.assertEqual(3, get_default_consumption(domain, product_id, 'wrong', 'useless'))
        self.assertEqual(2, get_default_consumption(domain, 'wrong', type_id, 'useless'))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, 'useless'))

    def testGetForId(self):
        _create_id_consumption(5)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(None, get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(None, get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(None, get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, supply_point_id))

        _create_type_consumption(4)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(4, get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(None, get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(None, get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, supply_point_id))

        _create_product_consumption(3)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(4, get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(3, get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(None, get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, supply_point_id))

        _create_domain_consumption(2)
        self.assertEqual(5, get_default_consumption(domain, product_id, type_id, supply_point_id))
        self.assertEqual(5, get_default_consumption(domain, product_id, 'useless', supply_point_id))
        self.assertEqual(4, get_default_consumption(domain, product_id, type_id, 'wrong'))
        self.assertEqual(3, get_default_consumption(domain, product_id, 'wrong', 'wrong'))
        self.assertEqual(2, get_default_consumption(domain, 'wrong', type_id, supply_point_id))
        self.assertEqual(None, get_default_consumption('wrong', product_id, type_id, supply_point_id))


def _create_domain_consumption(amt, domain=domain):
    DefaultConsumption(domain=domain, default_consumption=amt, type=TYPE_DOMAIN).save()

def _create_product_consumption(amt, domain=domain, product_id=product_id):
    DefaultConsumption(domain=domain, default_consumption=amt, type=TYPE_PRODUCT, product_id=product_id).save()

def _create_type_consumption(amt, domain=domain, product_id=product_id, type_id=type_id):
    DefaultConsumption(domain=domain, default_consumption=amt, type=TYPE_SUPPLY_POINT_TYPE, product_id=product_id,
                       supply_point_type=type_id).save()

def _create_id_consumption(amt, domain=domain, product_id=product_id, supply_point_id=supply_point_id):
    DefaultConsumption(domain=domain, default_consumption=amt, type=TYPE_SUPPLY_POINT, product_id=product_id,
                       supply_point_id=supply_point_id).save()
