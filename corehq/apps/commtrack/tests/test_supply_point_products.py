from datetime import datetime
from django.utils.unittest.case import TestCase
from corehq.apps.commtrack.helpers import make_supply_point,\
    make_supply_point_product, make_product, get_commtrack_user_id
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.cloudcare.tests.test_api import TEST_DOMAIN
from corehq.apps.commtrack import const

class SupplyPointProductTest(TestCase):

    def setUp(self):
        self.loc = make_loc('loc1')
        self.sp = make_supply_point(TEST_DOMAIN, self.loc)
        self.product = make_product(TEST_DOMAIN, 'product 1', 'p1')

    def tearDown(self):
        self.loc.delete()
        self.sp.delete()
        self.product.delete()

    def testMakeSupplyPointProduct(self):
        spp = make_supply_point_product(self.sp, self.product._id)
        self.assertEqual("CommCareCase", spp.doc_type)
        self.assertEqual(TEST_DOMAIN, spp.domain)
        self.assertEqual(const.SUPPLY_POINT_PRODUCT_CASE_TYPE, spp.type)
        self.assertEqual(self.product._id, spp.product)
        self.assertEqual(self.sp.location_, spp.location_)
        self.assertEqual(get_commtrack_user_id(TEST_DOMAIN), spp.user_id)
        self.assertEqual(None, spp.owner_id)
        self.assertFalse(spp.closed)
        self.assertTrue(len(spp.actions) > 0)
        [parent_ref] = spp.indices
        self.assertEqual(const.PARENT_CASE_REF, parent_ref.identifier)
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, parent_ref.referenced_type)
        self.assertEqual(self.sp._id, parent_ref.referenced_id)
        for dateprop in ('opened_on', 'modified_on', 'server_modified_on'):
            self.assertTrue(getattr(spp, dateprop) is not None)
            self.assertTrue(isinstance(getattr(spp, dateprop), datetime))

