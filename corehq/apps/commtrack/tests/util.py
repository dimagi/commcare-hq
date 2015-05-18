from django.test import TestCase
from lxml import etree

from casexml.apps.case.tests import delete_all_cases, delete_all_xforms
from casexml.apps.case.tests.util import delete_all_sync_logs
from casexml.apps.case.xml import V2
from casexml.apps.phone.tests.utils import generate_restore_payload
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from casexml.apps.stock.models import StockReport, StockTransaction
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_safe_write_kwargs

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import Location, LocationType
from corehq.apps.products.models import Product
from corehq.apps.sms.backend import test
from corehq.apps.users.models import CommCareUser

from .. import const
from ..helpers import make_supply_point
from ..models import SupplyPointCase, CommtrackConfig, ConsumptionConfig
from ..sms import StockReportParser, process
from ..util import get_default_requisition_config, get_or_create_default_program


TEST_DOMAIN = 'commtrack-test'
TEST_LOCATION_TYPE = 'outlet'
TEST_USER = 'commtrack-user'
TEST_NUMBER = '5551234'
TEST_PASSWORD = 'secret'
TEST_BACKEND = 'test-backend'

ROAMING_USER = {
    'username': TEST_USER + '-roaming',
    'phone_number': TEST_NUMBER,
    'first_name': 'roaming',
    'last_name': 'reporter',
    'user_data': {
        const.UserRequisitionRoles.REQUESTER: True,
        const.UserRequisitionRoles.RECEIVER: True,
    },
}

FIXED_USER = {
    'username': TEST_USER + '-fixed',
    'phone_number': str(int(TEST_NUMBER) + 1),
    'first_name': 'fixed',
    'last_name': 'reporter',
    'user_data': {
        const.UserRequisitionRoles.REQUESTER: True,
        const.UserRequisitionRoles.RECEIVER: True,
    },
    'home_loc': 'loc1',
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


def bootstrap_domain(domain_name=TEST_DOMAIN):
    # little test utility that makes a commtrack-enabled domain with
    # a default config and a location
    domain_obj = create_domain(domain_name)
    domain_obj.save(**get_safe_write_kwargs())
    domain_obj.convert_to_commtrack()
    return domain_obj


def bootstrap_user(setup, username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND, first_name='', last_name='',
                   home_loc=None, user_data=None,
                   ):
    user_data = user_data or {}
    user = CommCareUser.create(
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

        user.set_location(setup.loc)

    user.save_verified_number(domain, phone_number, verified=True, backend_id=backend)
    return CommCareUser.wrap(user.to_json())


def bootstrap_location_types(domain):
    previous = None
    for name, administrative in [
        ('state', True),
        ('district', True),
        ('block', True),
        ('village', True),
        ('outlet', False),
    ]:
        location_type, _ = LocationType.objects.get_or_create(
            domain=domain,
            name=name,
            defaults={
                'parent_type': previous,
                'administrative': administrative,
            },
        )
        previous = location_type


def make_product(domain, name, code, program_id):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.program_id = program_id
    p.save()
    return p


def bootstrap_products(domain):
    program = get_or_create_default_program(domain)
    make_product(domain, 'Sample Product 1', 'pp', program.get_id)
    make_product(domain, 'Sample Product 2', 'pq', program.get_id)
    make_product(domain, 'Sample Product 3', 'pr', program.get_id)


def make_loc(code, name=None, domain=TEST_DOMAIN, type=TEST_LOCATION_TYPE, parent=None):
    name = name or code
    LocationType.objects.get_or_create(domain=domain, name=type)
    loc = Location(site_code=code, name=name, domain=domain, location_type=type, parent=parent)
    loc.save()
    return loc


class CommTrackTest(TestCase):
    requisitions_enabled = False  # can be overridden
    user_definitions = []

    def setUp(self):
        # might as well clean house before doing anything
        delete_all_xforms()
        delete_all_cases()
        delete_all_sync_logs()

        StockReport.objects.all().delete()
        StockTransaction.objects.all().delete()

        self.backend = test.bootstrap(TEST_BACKEND, to_console=True)
        self.domain = bootstrap_domain()
        bootstrap_location_types(self.domain.name)
        bootstrap_products(self.domain.name)
        self.ct_settings = CommtrackConfig.for_domain(self.domain.name)
        self.ct_settings.consumption_config = ConsumptionConfig(
            min_transactions=0,
            min_window=0,
            optimal_window=60,
            min_periods=0,
        )
        if self.requisitions_enabled:
            self.ct_settings.requisition_config = get_default_requisition_config()

        self.ct_settings.save()

        self.domain = Domain.get(self.domain._id)

        self.loc = make_loc('loc1')
        self.sp = make_supply_point(self.domain.name, self.loc)
        self.users = [bootstrap_user(self, **user_def) for user_def in self.user_definitions]

        if False:
            # bootstrap additional users for requisitions
            # needs to get reinserted for requisition stuff later
            self.approver = bootstrap_user(self, **APPROVER_USER)
            self.packer = bootstrap_user(self, **PACKER_USER)
            self.users += [self.approver, self.packer]

        # everyone should be in a group.
        self.group = Group(domain=TEST_DOMAIN, name='commtrack-folks',
                           users=[u._id for u in self.users],
                           case_sharing=True)
        self.group.save()
        self.sp.owner_id = self.group._id
        self.sp.save()
        self.products = sorted(Product.by_domain(self.domain.name), key=lambda p: p._id)
        self.assertEqual(3, len(self.products))

    def tearDown(self):
        self.backend.delete()
        for u in self.users:
            u.delete()
        self.domain.delete() # domain delete cascades to everything else

    def get_commtrack_forms(self, domain):
        return XFormInstance.view('reports_forms/all_forms',
            startkey=['submission xmlns', domain, COMMTRACK_REPORT_XMLNS],
            endkey=['submission xmlns', domain, COMMTRACK_REPORT_XMLNS, {}],
            reduce=False,
            include_docs=True
        )


def get_ota_balance_xml(user):
    xml = generate_restore_payload(user.to_casexml_user(), version=V2)
    return extract_balance_xml(xml)


def extract_balance_xml(xml_payload):
    balance_blocks = etree.fromstring(xml_payload).findall('{http://commcarehq.org/ledger/v1}balance')
    if balance_blocks:
        return [etree.tostring(bb) for bb in balance_blocks]
    return []


def fake_sms(user, text):
    """
    Fake a commtrack SMS submission for a user.
    `text` might be "soh myproduct 100"
    Don't use this with a real user
    """
    if not user.phone_number:
        raise ValueError("User does not have a phone number")
    if not user.get_verified_number():
        user.save_verified_number(user.domain, user.phone_number, True, None)
    domain_obj = Domain.get_by_name(user.domain)
    parser = StockReportParser(domain_obj, user.get_verified_number())
    process(user.domain, parser.parse(text.lower()))
