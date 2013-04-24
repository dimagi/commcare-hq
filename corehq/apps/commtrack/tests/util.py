from casexml.apps.case.tests import delete_all_cases, delete_all_xforms
from corehq.apps.commtrack import const
from corehq.apps.locations.models import Location
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.commtrack.util import bootstrap_default
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms.backend import test
from django.utils.unittest.case import TestCase
from corehq.apps.commtrack.helpers import make_supply_point,\
    make_supply_point_product
from corehq.apps.commtrack.models import Product
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_safe_write_kwargs

TEST_DOMAIN = 'commtrack-test'
TEST_LOCATION_TYPE = 'location'
TEST_USER = 'commtrack-user'
TEST_NUMBER = '5551234'
TEST_PASSWORD = 'secret'
TEST_BACKEND = 'test-backend'

def bootstrap_domain(domain_name=TEST_DOMAIN, requisitions_enabled=False):
    # little test utility that makes a commtrack-enabled domain with
    # a default config and a location
    domain_obj = create_domain(domain_name)
    domain_obj.commtrack_enabled = True
    domain_obj.save(**get_safe_write_kwargs())
    bootstrap_default(domain_name, requisitions_enabled)
    return domain_obj


def bootstrap_user(username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND):
    user = CommCareUser.create(domain, username, password, phone_numbers=[TEST_NUMBER])
    user.save_verified_number(domain, phone_number, verified=True, backend_id=TEST_BACKEND)
    return user

def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE):
    name = name or code
    loc = Location(site_code=code, name=name, domain=domain, type=type)
    loc.save()
    return loc

class CommTrackTest(TestCase):
    requisitions_enabled = False # can be overridden

    def setUp(self):
        # might as well clean house before doing anything
        delete_all_xforms()
        delete_all_cases()

        self.backend = test.bootstrap(TEST_BACKEND, to_console=True)
        self.domain = bootstrap_domain(requisitions_enabled=self.requisitions_enabled)
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
        self.backend.delete()
        self.user.delete()
        self.domain.delete() # domain delete cascades to everything else

    def get_commtrack_forms(self):
        return XFormInstance.view('couchforms/by_xmlns',
            key=const.COMMTRACK_REPORT_XMLNS,
            reduce=False,
            include_docs=True
        )