from django.utils.unittest.case import TestCase
from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import make_loc, TEST_DOMAIN


class SupplyPointTest(TestCase):

    def setUp(self):
        self.loc = make_loc('loc1')

    def tearDown(self):
        self.loc.delete()

    def testMakeSupplyPoint(self):
        sp = make_supply_point(TEST_DOMAIN, self.loc)
        self.assertEqual("CommCareCase", sp.doc_type)
        self.assertEqual(TEST_DOMAIN, sp.domain)
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, sp.type)
        self.assertEqual([self.loc._id], sp.location_)
        # rest to be fleshed out once making supply points does more

