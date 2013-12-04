import logging
from casexml.apps.case.mock import CaseBlock
from corehq.apps.commtrack.models import Product, CommtrackConfig,\
    CommtrackActionConfig, SupplyPointType, SupplyPointProductCase, SupplyPointCase
from corehq.apps.commtrack import const
from casexml.apps.case.xml import V2
import uuid
from corehq.apps.hqcase.utils import submit_case_blocks
from xml.etree import ElementTree
from corehq.apps.users.cases import get_owner_id, reconcile_ownership

"""
helper code to populate the various commtrack models, for ease of
development/testing, before we have proper UIs and imports
"""

def make_product(domain, name, code):
    p = Product()
    p.domain = domain
    p.name = name
    p.code = code.lower()
    p.save()
    return p

def make_supply_point(domain, location, owner_id=None):
    return SupplyPointCase.create_from_location(domain, location, owner_id)

def make_supply_point_product(supply_point_case, product_uuid, owner_id=None):
    domain = supply_point_case.domain
    id = uuid.uuid4().hex
    user_id = const.get_commtrack_user_id(domain)
    owner_id = owner_id or get_owner_id(supply_point_case) or user_id
    username = const.COMMTRACK_USERNAME
    product_name = Product.get(product_uuid).name
    caseblock = CaseBlock(
        case_id=id,
        create=True,
        version=V2,
        case_name=product_name,
        user_id=user_id,
        owner_id=owner_id,
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
    submit_case_blocks(casexml, domain, username, user_id,
                       xmlns=const.COMMTRACK_SUPPLY_POINT_PRODUCT_XMLNS)
    sppc = SupplyPointProductCase.get(id)
    sppc.bind_to_location(supply_point_case.location)
    sppc.save()
    return sppc

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
            SupplyPointType(name='RP', categories=['Traditional']),
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
