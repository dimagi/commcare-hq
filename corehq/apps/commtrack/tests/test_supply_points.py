from corehq.apps.commtrack.helpers import make_supply_point,\
    get_commtrack_user_id
from corehq.apps.commtrack import const
from corehq.apps.commtrack.tests.util import (make_loc, TEST_DOMAIN,
    CommTrackTest)
from corehq.apps.commtrack.models import SupplyPointCase
from datetime import datetime

class SupplyPointTest(CommTrackTest):

    def setUp(self):
        super(SupplyPointTest, self).setUp()
        self.loc = make_loc('loc1')

    def tearDown(self):
        self.loc.delete()
        super(CommTrackTest, self).tearDown()

    def testMakeSupplyPoint(self):
        sp = make_supply_point(TEST_DOMAIN, self.loc)
        self.assertIsInstance(sp, SupplyPointCase)
        self.assertEqual("CommCareCase", sp.doc_type)
        self.assertEqual(TEST_DOMAIN, sp.domain)
        self.assertEqual(const.SUPPLY_POINT_CASE_TYPE, sp.type)
        self.assertEqual([self.loc._id], sp.location_)
        self.assertEqual(get_commtrack_user_id(TEST_DOMAIN), sp.user_id)
        self.assertEqual(sp.user_id, sp.owner_id)
        self.assertFalse(sp.closed)
        self.assertTrue(len(sp.actions) > 0)
        for dateprop in ('opened_on', 'modified_on', 'server_modified_on'):
            self.assertTrue(getattr(sp, dateprop) is not None)
            self.assertTrue(isinstance(getattr(sp, dateprop), datetime))

    def testMakeOwnedSupplyPoint(self):
        sp = make_supply_point(TEST_DOMAIN, self.loc, 'some-other-owner')
        self.assertEqual(get_commtrack_user_id(TEST_DOMAIN), sp.user_id)
        self.assertEqual('some-other-owner', sp.owner_id)
