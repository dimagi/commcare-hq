from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import Product, CommtrackConfig,\
    CommtrackActionConfig, SupplyPointType
from corehq.apps.commtrack import const
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
import uuid
from corehq.apps.hqcase.utils import submit_case_blocks
from xml.etree import ElementTree

"""
helper code to populate the various commtrack models, for ease of
development/testing, before we have proper UIs and imports
"""

def get_commtrack_user_id(domain):
    # abstracted out in case we one day want to back this
    # by a real user, but for now it's like demo_user
    return const.COMMTRACK_USERNAME

def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p

def make_supply_point(domain, location):
    # a supply point is currently just a case with a special type
    id = uuid.uuid4().hex
    user_id = get_commtrack_user_id(domain)
    username = const.COMMTRACK_USERNAME
    caseblock = CaseBlock(
        case_id=id,
        create=True,
        version=V2,
        user_id=user_id,
        case_type=const.SUPPLY_POINT_CASE_TYPE,
    )
    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, domain, username, user_id)
    c = CommCareCase.get(id)
    c.bind_to_location(location)
    c.save()
    return c

def make_supply_point_product(supply_point_case, product_uuid):
    domain = supply_point_case.domain
    id = uuid.uuid4().hex
    user_id = get_commtrack_user_id(domain)
    username = const.COMMTRACK_USERNAME
    caseblock = CaseBlock(
        case_id=id,
        create=True,
        version=V2,
        user_id=user_id,
        case_type=const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
        update={
            "product": product_uuid
        },
        index={
            const.PARENT_CASE_REF: (const.SUPPLY_POINT_CASE_TYPE,
                                    supply_point_case._id),
        }
    )
    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, domain, username, user_id)
    pc = CommCareCase.get(id)
    pc.location_ = supply_point_case.location_
    pc.save()
    return pc

def make_psi_config(domain):
    c = CommtrackConfig(
        domain=domain,
        multiaction_enabled=True,
        multiaction_keyword='s',
        actions=[
            CommtrackActionConfig(
                action_type='stockedoutfor',
                keyword='d',
                caption='Stock-out Days'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                keyword='r',
                caption='Other Receipts'
            ),
            CommtrackActionConfig(
                action_type='stockonhand',
                keyword='b',
                caption='Balance'
            ),
            CommtrackActionConfig(
                action_type='receipts',
                name='sales',
                keyword='p',
                caption='Placements'
            ),
        ],
        supply_point_types=[
            SupplyPointType(name='CHC', categories=['Public']),
            SupplyPointType(name='PHC', categories=['Public']),
            SupplyPointType(name='SC', categories=['Public']),
            SupplyPointType(name='MBBS', categories=['Private']),
            SupplyPointType(name='Pediatrician', categories=['Private']),
            SupplyPointType(name='AYUSH', categories=['Private']),
            SupplyPointType(name='Medical Store / Chemist', categories=['Traditional']),
            SupplyPointType(name='RMP', categories=['Traditional']),
            SupplyPointType(name='Asha', categories=['Frontline Workers']),
            SupplyPointType(name='AWW', categories=['Public', 'Frontline Workers']),
            SupplyPointType(name='NGO', categories=['Non-traditional']),
            SupplyPointType(name='CBO', categories=['Non-traditional']),
            SupplyPointType(name='SHG', categories=['Non-traditional']),
            SupplyPointType(name='Pan Store', categories=['Traditional']),
            SupplyPointType(name='General Store', categories=['Traditional']),
        ]
    )
    c.save()
    return c

    
