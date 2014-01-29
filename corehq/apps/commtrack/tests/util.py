import uuid
from xml.etree import ElementTree
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests import delete_all_cases, delete_all_xforms
from casexml.apps.case.xml import V2
from corehq.apps.commtrack import const
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import Location
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.commtrack.util import bootstrap_commtrack_settings_if_necessary
from corehq.apps.commtrack.models import CommTrackUser, SupplyPointCase
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

REPORTING_USERS = {
    'roaming': {
        'username': TEST_USER + '-roaming',
        'phone_number': TEST_NUMBER,
        'first_name': 'roaming',
        'last_name': 'reporter',
        'user_data': {
            const.UserRequisitionRoles.REQUESTER: True,
            const.UserRequisitionRoles.RECEIVER: True,
        },
    },
    'fixed': {
        'username': TEST_USER + '-fixed',
        'phone_number': str(int(TEST_NUMBER) + 1),
        'first_name': 'fixed',
        'last_name': 'reporter',
        'user_data': {
            const.UserRequisitionRoles.REQUESTER: True,
            const.UserRequisitionRoles.RECEIVER: True,
        },
        'home_loc': 'loc1',
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
    bootstrap_commtrack_settings_if_necessary(domain_obj, requisitions_enabled)

    return domain_obj


def bootstrap_user(setup, username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND, first_name='', last_name='',
                   home_loc=None, user_data=None,
                   ):
    user_data = user_data or {}
    user = CommTrackUser.create(
        domain,
        username,
        password,
        phone_numbers=[TEST_NUMBER],
        user_data=user_data,
        first_name=first_name,
        last_name=last_name
    )
    if home_loc == setup.loc.site_code:
        if not SupplyPointCase.get_by_location(setup.loc):
            make_supply_point(domain, setup.loc)

        user.add_location(setup.loc)
        user.save()

    user.save_verified_number(domain, phone_number, verified=True, backend_id=backend)
    return CommTrackUser.wrap(user.to_json())

def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE, parent=None):
    name = name or code
    loc = Location(site_code=code, name=name, domain=domain, type=type, parent=parent)
    loc.save()
    return loc

def update_supply_point_product_stock_level(spp, current_stock):
    caseblock = CaseBlock(
        case_id=spp._id,
        create=False,
        version=V2,
        user_id=spp.user_id,
        owner_id=spp.owner_id,
        case_type=const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
        update={
            "current_stock": current_stock
        },
    )
    username = const.COMMTRACK_USERNAME
    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, spp.domain, username, spp.user_id,
                       xmlns=const.COMMTRACK_SUPPLY_POINT_PRODUCT_XMLNS)

class CommTrackTest(TestCase):
    requisitions_enabled = False # can be overridden

    def setUp(self):
        # might as well clean house before doing anything
        delete_all_xforms()
        delete_all_cases()

        self.backend = test.bootstrap(TEST_BACKEND, to_console=True)
        self.domain = bootstrap_domain(requisitions_enabled=self.requisitions_enabled)
        self.loc = make_loc('loc1')
        self.sp = make_supply_point(self.domain.name, self.loc)

        self.reporters = dict((k, bootstrap_user(self, **v)) for k, v in REPORTING_USERS.iteritems())
        # backwards compatibility
        self.user = self.reporters['roaming']

        # bootstrap additional users for requisitions
        self.approver = bootstrap_user(self, **APPROVER_USER)
        self.packer = bootstrap_user(self, **PACKER_USER)

        self.users = self.reporters.values() + [self.approver, self.packer]
        # everyone should be in a group.
        self.group = Group(domain=TEST_DOMAIN, name='commtrack-folks',
                           users=[u._id for u in self.users],
                           case_sharing=True)
        self.group.save()
        self.sp.owner_id = self.group._id
        self.sp.save()

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
