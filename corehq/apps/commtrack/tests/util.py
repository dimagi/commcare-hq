from datetime import datetime

from lxml import etree

from casexml.apps.phone.utils import MockDevice
from casexml.apps.stock.const import SECTION_TYPE_STOCK
from dimagi.utils.couch.database import get_safe_write_kwargs
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, make_location
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.parsers.ledgers.helpers import (
    StockTransactionHelper,
)
from corehq.util.decorators import require_debug_true

from ..const import StockActions
from ..sms import to_instance
from ..util import get_or_create_default_program, get_supply_point_and_location

TEST_DOMAIN = 'commtrack-test'
TEST_LOCATION_TYPE = 'outlet'
TEST_USER = 'commtrack-user'
TEST_NUMBER = '5551234'
TEST_PASSWORD = 'secret'
TEST_BACKEND = 'MOBILE_BACKEND_TEST'

ROAMING_USER = {
    'username': TEST_USER + '-roaming',
    'phone_number': TEST_NUMBER,
    'first_name': 'roaming',
    'last_name': 'reporter',
    'user_data': {},
}

FIXED_USER = {
    'username': TEST_USER + '-fixed',
    'phone_number': str(int(TEST_NUMBER) + 1),
    'first_name': 'fixed',
    'last_name': 'reporter',
    'user_data': {},
    'home_loc': 'loc1',
}


def bootstrap_domain(domain_name):
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
    user = CommCareUser.create(
        domain,
        username,
        password,
        created_by=None,
        created_via=None,
        phone_numbers=[TEST_NUMBER],
        user_data=user_data,
        first_name=first_name,
        last_name=last_name
    )
    if home_loc == setup.loc.site_code:
        user.set_location(setup.loc)

    entry = user.get_or_create_phone_entry(phone_number)
    entry.set_two_way()
    entry.set_verified()
    entry.backend_id = backend
    entry.save()
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
    if not Domain.get_by_name(domain):
        raise AssertionError("You can't make a location on a fake domain")
    name = name or code
    LocationType.objects.get_or_create(domain=domain, name=type,
                                       defaults={'administrative': False})
    loc = make_location(site_code=code, name=name, domain=domain, location_type=type, parent=parent)
    loc.save()
    return loc


def get_ota_balance_xml(project, user):
    device = MockDevice(project, user.to_ota_restore_user(project.name))
    return extract_balance_xml(device.sync().payload)


def extract_balance_xml(xml_payload):
    balance_blocks = etree.fromstring(xml_payload).findall('{http://commcarehq.org/ledger/v1}balance')
    if balance_blocks:
        return [etree.tostring(bb, encoding='utf-8') for bb in balance_blocks]
    return []


def get_single_balance_block(case_id, product_id, quantity, date_string=None, section_id='stock', type=None):
    date_string = date_string or json_format_datetime(datetime.utcnow())
    return """
<balance xmlns="http://commcarehq.org/ledger/v1" entity-id="{case_id}" date="{date}" section-id="{section_id}"{type}>
    <entry id="{product_id}" quantity="{quantity}" />
</balance>""".format(
        case_id=case_id, product_id=product_id, quantity=quantity, date=date_string, section_id=section_id,
        type=' type="{}"'.format(type) if type else ''
    ).strip()


def get_single_transfer_block(src_id, dest_id, product_id, quantity, date_string=None, section_id='stock'):
    date_string = date_string or json_format_datetime(datetime.utcnow())
    return """
<transfer xmlns="http://commcarehq.org/ledger/v1" {src} {dest} date="{date}" section-id="{section_id}">
    <entry id="{product_id}" quantity="{quantity}" />
</transfer >""".format(
        src='src="{}"'.format(src_id) if src_id is not None else '',
        dest='dest="{}"'.format(dest_id) if dest_id is not None else '',
        product_id=product_id, quantity=quantity,
        date=date_string, section_id=section_id,
    ).strip()


@require_debug_true()
def submit_stock_update(user, site_code, product_code, balance):
    """For local testing only."""
    case, location = get_supply_point_and_location(user.domain, site_code)
    product = SQLProduct.objects.get(domain=user.domain, code=product_code)

    tx = StockTransactionHelper(
        product_id=product.product_id,
        action=StockActions.STOCKONHAND,
        domain=user.domain,
        quantity=balance,
        location_id=location.location_id,
        timestamp=datetime.utcnow(),
        case_id=case.case_id,
        section_id=SECTION_TYPE_STOCK,
    )
    xml = to_instance({
        'timestamp': datetime.utcnow(),
        'user': user,
        'phone': user.phone_number or '8675309',
        'location': location,
        'transactions': [tx],
    })
    submit_form_locally(
        instance=xml,
        domain=user.domain,
    )
