'''
Created on Feb 28, 2013

@author: czue
'''
from corehq.apps.commtrack.const import RequisitionActions
import uuid
from corehq.apps.users.models import CouchUser
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.commtrack import const
from xml.etree import ElementTree
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.models import CommCareCase


def create_requisition(product_stock_case, transaction):
    assert transaction.action_config.action_type == RequisitionActions.REQUEST
    domain = product_stock_case.domain
    id = uuid.uuid4().hex
    user_id = transaction.user_id
    username = CouchUser.get(user_id).username
    caseblock = CaseBlock(
        case_id=id,
        create=True,
        version=V2,
        user_id=user_id,
        case_type=const.REQUISITION_CASE_TYPE,
        update={
            "amount_requested": str(transaction.value)
        },
        index={
            const.PARENT_CASE_REF: (const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
                                    product_stock_case._id),
        }
    )
    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, domain, username, user_id)
    case = CommCareCase.get(id)
    # NOTE: should these have locations?
    # case.location_ = supply_point_case.location_
    return case


    