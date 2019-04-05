from __future__ import absolute_import
from __future__ import unicode_literals
import six
import uuid

from casexml.apps.case.mock import CaseBlock
from corehq.apps.commtrack import const
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.products.models import Product
from corehq.form_processor.interfaces.supply import SupplyInterface

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


def make_supply_point(domain, location):
    # a supply point is currently just a case with a special type
    case_id = uuid.uuid4().hex
    if six.PY2:
        case_id = case_id.decode('utf-8')
    user_id = const.get_commtrack_user_id(domain)
    owner_id = location.location_id
    kwargs = {'external_id': location.external_id} if location.external_id else {}
    caseblock = CaseBlock(
        case_id=case_id,
        create=True,
        case_name=location.name,
        user_id=user_id,
        owner_id=owner_id,
        case_type=const.SUPPLY_POINT_CASE_TYPE,
        update={
            'location_id': location.location_id,
        },
        **kwargs
    )
    _submit_commtrack_caseblock(domain, caseblock, "make_supply_point")
    return SupplyInterface(domain).get_supply_point(case_id)


def update_supply_point_from_location(supply_point, location):
    domain = supply_point.domain
    assert domain == location.domain

    are_different = (
        supply_point.external_id != location.external_id or
        supply_point.name != location.name or
        supply_point.location_id != location.location_id
    )

    if are_different:
        kwargs = {'external_id': location.external_id} if location.external_id else {}
        caseblock = CaseBlock(
            case_id=supply_point.case_id,
            create=False,
            case_name=location.name,
            user_id=const.get_commtrack_user_id(location.domain),
            update={
                'location_id': location.location_id,
            },
            **kwargs
        )
        _submit_commtrack_caseblock(domain, caseblock, "update_supply_point_from_location")
        return SupplyInterface(domain).get_supply_point(supply_point.case_id)
    else:
        return supply_point


def _submit_commtrack_caseblock(domain, caseblock, source):
    submit_case_blocks(
        caseblock.as_string().decode('utf-8'),
        domain,
        const.COMMTRACK_USERNAME,
        const.get_commtrack_user_id(domain),
        xmlns=const.COMMTRACK_SUPPLY_POINT_XMLNS,
        device_id=__name__ + "." + source,
    )
