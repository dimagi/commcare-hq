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

class RequisitionState(object):
    """
    Intermediate representation of a requisition
    """

    def __init__(self, domain, id, user_id, username, product_stock_case_id,
                 create=False, amount_requested=None):
        self.domain = domain
        self.id = id
        self.user_id = user_id
        self.username = username
        self.product_stock_case_id = product_stock_case_id
        self.create = create
        self.amount_requested = amount_requested

    def to_xml(self):
        caseblock = CaseBlock(
            case_id=self.id,
            create=self.create,
            version=V2,
            user_id=self.user_id,
            case_type=const.REQUISITION_CASE_TYPE,
            update={
                "amount_requested": str(self.amount_requested)
            },
            index={
                const.PARENT_CASE_REF: (const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
                                        self.product_stock_case_id),
            }
        )
        return ElementTree.tostring(caseblock.as_xml())

    @classmethod
    def from_transactions(cls, product_stock_case, transactions):
        def _to_fields(transaction):
            # TODO support other types
            if transaction.action_config.action_type == RequisitionActions.REQUEST:
                return {
                    'create':           True,
                    'amount_requested': transaction.value,
                }
            else:
                raise ValueError('only requests are currently supported')

        user_id = None
        kwargs = {}
        for tx in transactions:
            if user_id is None:
                user_id = tx.user_id
            else:
                assert user_id == tx.user_id, 'all transaction user ids should match'

            fields = _to_fields(tx)
            for field in fields:
                assert field not in kwargs, 'transaction updates should be disjoint but found %s twice' % field
            kwargs.update(fields)

        username = CouchUser.get(user_id).username
        return RequisitionState(
            domain=product_stock_case.domain,
            id=uuid.uuid4().hex, # TODO: support non-create case
            user_id=user_id,
            username=username,
            product_stock_case_id=product_stock_case._id,
            **kwargs
        )

def create_requisition(product_stock_case, transaction):
    req = RequisitionState.from_transactions(product_stock_case, [transaction])
    submit_case_blocks(req.to_xml(), req.domain, req.username,
                       req.user_id)
    case = CommCareCase.get(req.id)
    # NOTE: should these have locations?
    # case.location_ = supply_point_case.location_
    return case

