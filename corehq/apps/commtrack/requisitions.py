'''
Created on Feb 28, 2013

@author: czue
'''
from copy import copy
from datetime import datetime
from corehq.apps.commtrack.const import RequisitionActions, RequisitionStatus
import uuid
from corehq.apps.commtrack.models import RequisitionCase
from corehq.apps.users.models import CouchUser
from casexml.apps.case.tests.util import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.commtrack import const
from xml.etree import ElementTree
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_datetime


class RequisitionState(object):
    """
    Intermediate representation of a requisition
    """

    def __init__(self, domain, id, user_id, username, product_stock_case_id,
                 create=False, **custom_fields):
        self.domain = domain
        self.id = id
        self.user_id = user_id
        self.username = username
        self.product_stock_case_id = product_stock_case_id
        self.create = create
        self.custom_fields = custom_fields or {}

    def to_xml(self):
        caseblock = CaseBlock(
            case_id=self.id,
            create=self.create,
            version=V2,
            user_id=self.user_id,
            case_type=const.REQUISITION_CASE_TYPE,
            update = copy(self.custom_fields),
            index={
                const.PARENT_CASE_REF: (const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
                                        self.product_stock_case_id),
            }
        )
        return ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime))

    @classmethod
    def from_transactions(cls, user_id, product_stock_case, transactions):
        assert transactions, "can't make a requisition state from an empty transaciton list"

        def _to_fields(transaction):
            ret = {'requisition_status': RequisitionStatus.by_action_type(transaction.action_config.action_type)}
            if transaction.action_config.action_type == RequisitionActions.REQUEST:
                ret.update({
                    'create': True,
                    'amount_requested': transaction.value,
                    'product_id': product_stock_case.product,
                    'requested_by': user_id,
                    'requested_on': datetime.utcnow(),
                })
            elif transaction.action_config.action_type == RequisitionActions.APPROVAL:
                ret.update({
                    'amount_approved': transaction.value,
                    'approved_by': user_id,
                    'approved_on': datetime.utcnow(),
                })
            elif transaction.action_config.action_type == RequisitionActions.FILL:
                ret.update({
                    'amount_filled': transaction.value,
                    'filled_by': user_id,
                    'filled_on': datetime.utcnow(),
                })
            else:
                raise ValueError("the type %s isn't yet supported." % transaction.action_config.action_type)
            return ret

        def _get_case_id(transactions):
            req_case_id = None
            for tx in transactions:
                if tx.requisition_case_id:
                    if req_case_id:
                        assert tx.requisition_case_id == req_case_id, 'tried to update multiple cases with one set of transactions'
                    req_case_id = tx.requisition_case_id
            return req_case_id or uuid.uuid4().hex

        kwargs = {}
        for tx in transactions:
            fields = _to_fields(tx)
            for field in fields:
                assert field not in kwargs, 'transaction updates should be disjoint but found %s twice' % field
            kwargs.update(fields)

        username = CouchUser.get(user_id).username

        return cls(
            domain=product_stock_case.domain,
            id=_get_case_id(transactions),
            user_id=user_id,
            username=username,
            product_stock_case_id=product_stock_case._id,
            **kwargs
        )

def create_requisition(user_id, product_stock_case, transaction):
    req = RequisitionState.from_transactions(user_id, product_stock_case, [transaction])
    submit_case_blocks(req.to_xml(), req.domain, req.username,
                       req.user_id)
    case = RequisitionCase.get(req.id)
    case.location_ = product_stock_case.location_
    return case

