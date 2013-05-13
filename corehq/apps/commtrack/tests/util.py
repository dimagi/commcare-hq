from casexml.apps.case.tests import delete_all_cases, delete_all_xforms
from corehq.apps.commtrack import const
from corehq.apps.groups.models import Group
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

MAIN_USER = {
    'username': TEST_USER,
    'phone_number': TEST_NUMBER,
    'first_name': 'main',
    'last_name': 'user',
    'user_data': {
        const.UserRequisitionRoles.REQUESTER: True,
        const.UserRequisitionRoles.RECEIVER: True,
    },
}
APPROVER_USER = {
    'username': 'test-approver',
    'phone_number': '5550000',
    'first_name': 'approver',
    'last_name': 'user',
    'user_data': {
        const.UserRequisitionRoles.APPROVER: True,
    },
}

PACKER_USER = {
    'username': 'test-packer',
    'phone_number': '5550001',
    'first_name': 'packer',
    'last_name': 'user',
    'user_data': {
        const.UserRequisitionRoles.SUPPLIER: True,
    },
}

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
                   backend=TEST_BACKEND, first_name='', last_name='',
                   user_data=None,
                   ):
    user_data = user_data or {}
    user = CommCareUser.create(domain, username, password, phone_numbers=[TEST_NUMBER],
                               user_data=user_data, first_name=first_name,
                               last_name=last_name)
    user.save_verified_number(domain, phone_number, verified=True, backend_id=backend)
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
        self.user = bootstrap_user(**MAIN_USER)
        self.verified_number = self.user.get_verified_number()

        # bootstrap additional users for requisitions
        self.approver = bootstrap_user(**APPROVER_USER)
        self.packer = bootstrap_user(**PACKER_USER)

        self.users = [self.user, self.approver, self.packer]
        # everyone should be in a group.
        self.group = Group(domain=TEST_DOMAIN, name='commtrack-folks',
                           users=[u._id for u in self.users],
                           case_sharing=True)
        self.group.save()

        self.loc = make_loc('loc1')
        self.sp = make_supply_point(self.domain.name, self.loc, owner_id=self.group._id)
        self.products = Product.by_domain(self.domain.name)
        self.assertEqual(3, len(self.products))
        self.spps = {}
        for p in self.products:
            self.spps[p.code] = make_supply_point_product(self.sp, p._id)
            self.assertEqual(self.spps[p.code].owner_id, self.group._id)

    def tearDown(self):
        self.backend.delete()
        for u in self.users:
            u.delete()
        self.domain.delete() # domain delete cascades to everything else

    def get_commtrack_forms(self):
        return XFormInstance.view('couchforms/by_xmlns',
            key=const.COMMTRACK_REPORT_XMLNS,
            reduce=False,
            include_docs=True
        )
