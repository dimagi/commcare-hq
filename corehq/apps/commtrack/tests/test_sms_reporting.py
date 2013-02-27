from django.utils.unittest.case import TestCase
from corehq.apps.commtrack.helpers import make_supply_point,\
    make_supply_point_product
from corehq.apps.commtrack.tests.util import make_loc, \
    bootstrap_domain, bootstrap_user, TEST_BACKEND
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.sms import handle
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.backend import test

class StockReportTest(TestCase):

    def setUp(self):
        self.backend = test.bootstrap(TEST_BACKEND, to_console=True)
        self.domain = bootstrap_domain()
        self.user = bootstrap_user()
        self.verified_number = self.user.get_verified_number()
        self.loc = make_loc('loc1')
        self.sp = make_supply_point(self.domain.name, self.loc)
        self.products = Product.by_domain(self.domain.name)
        self.assertEqual(3, len(self.products))
        self.spps = {}
        for p in self.products:
            self.spps[p.code] = make_supply_point_product(self.sp, p._id)

    def tearDown(self):
        self.domain.delete() # domain delete cascades to everything else

    def testStockReport(self):
        amounts = {
            'pp': 10,
            'pq': 20,
            'pr': 30,
        }
        # soh loc1 pp 10 pq 20...
        handled = handle(self.verified_number, 'soh {loc} {report}'.format(
            loc='loc1',
            report=' '.join('%s %s' % (k, v) for k, v in amounts.items())
        ))
        self.assertTrue(handled)
        for code, amt in amounts.items():
            spp = CommCareCase.get(self.spps[code]._id)
            self.assertEqual(str(amt), spp.current_stock)
