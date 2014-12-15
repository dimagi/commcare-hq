from django.test import TestCase

from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import (make_loc, TEST_DOMAIN,
    bootstrap_domain)
from datetime import datetime

class SupplyPointTest(TestCase):

    def setUp(self):
        self.domain = bootstrap_domain(TEST_DOMAIN)
        self.loc = make_loc('loc1')

    def tearDown(self):
        self.loc.delete()
        self.domain.delete()

    def testMakeSupplyPoint(self):
        sp = make_supply_point(TEST_DOMAIN, self.loc)
        self.assertEqual("CommCareCase", sp.doc_type)
        self.assertEqual(self.loc.name, sp.name)
        self.assertEqual(TEST_DOMAIN, sp.domain)
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, sp.type)
        self.assertEqual(self.loc._id, sp.location_id)
        self.assertEqual(const.get_commtrack_user_id(TEST_DOMAIN), sp.user_id)
        self.assertEqual(sp.user_id, sp.owner_id)
        self.assertFalse(sp.closed)
        self.assertTrue(len(sp.actions) > 0)
        for dateprop in ('opened_on', 'modified_on', 'server_modified_on'):
            self.assertTrue(getattr(sp, dateprop) is not None)
            self.assertTrue(isinstance(getattr(sp, dateprop), datetime))

    def testMakeOwnedSupplyPoint(self):
        sp = make_supply_point(TEST_DOMAIN, self.loc, 'some-other-owner')
        self.assertEqual(const.get_commtrack_user_id(TEST_DOMAIN), sp.user_id)
        self.assertEqual('some-other-owner', sp.owner_id)
