'''
Created on Feb 28, 2013

@author: czue
'''
from copy import copy
from datetime import datetime
from casexml.apps.case.mock import CaseBlock
from corehq.apps.commtrack.const import RequisitionActions, RequisitionStatus, UserRequisitionRoles, notification_template
import uuid
from corehq.apps.commtrack.models import RequisitionCase
from corehq.apps.users.cases import get_owning_users, get_owner_id
from corehq.apps.users.models import CouchUser
from casexml.apps.case.xml import V2
from corehq.apps.commtrack import const
from xml.etree import ElementTree
from corehq.apps.hqcase.utils import submit_case_blocks
from dimagi.utils.parsing import json_format_datetime

class RequisitionState(object):
    """
    Intermediate representation of a requisition
    """

    def __init__(self, domain, id, user_id, username, product_stock_case,
                 create=False, owner_id=None, close=False, **custom_fields):
        self.domain = domain
        self.id = id
        self.user_id = user_id
        self.owner_id = owner_id
        self.username = username
        self.product_stock_case = product_stock_case
        self.create = create
        self.close = close
        self.custom_fields = custom_fields or {}

    def to_xml(self):
        extras = {}
        if self.owner_id:
            extras['owner_id'] = self.owner_id
        if self.create:
            extras['case_name'] = self.product_stock_case.name
            extras['index'] = {
                const.PARENT_CASE_REF: (const.SUPPLY_POINT_PRODUCT_CASE_TYPE,
                                        self.product_stock_case._id),
            }
        caseblock = CaseBlock(
            case_id=self.id,
            create=self.create,
            version=V2,
            user_id=self.user_id,
            case_type=const.REQUISITION_CASE_TYPE,
            update = copy(self.custom_fields),
            close=self.close,
            **extras
        )
        return ElementTree.tostring(caseblock.as_xml(format_datetime=json_format_datetime))

    @classmethod
    def from_transactions(cls, user_id, product_stock_case, transactions):
        assert transactions, "can't make a requisition state from an empty transaction list"

        def _to_fields(transaction):
            ret = {'requisition_status': RequisitionStatus.by_action_type(transaction.action_config.action_type)}
            if transaction.action_config.action_type == RequisitionActions.REQUEST:
                ret.update({
                    'create': True,
                    'owner_id': get_owner_id(product_stock_case) or user_id,
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
            elif transaction.action_config.action_type == RequisitionActions.PACK:
                ret.update({
                    'amount_packed': transaction.value,
                    'packed_by': user_id,
                    'packed_on': datetime.utcnow(),
                })
            elif transaction.action_config.action_type == RequisitionActions.RECEIPTS:
                ret.update({
                    'amount_received': transaction.value,
                    'received_by': user_id,
                    'received_on': datetime.utcnow(),
                    'close': True,
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
            product_stock_case=product_stock_case,
            **kwargs
        )


def create_requisition(user_id, product_stock_case, transaction):
    req = RequisitionState.from_transactions(user_id, product_stock_case, [transaction])
    submit_case_blocks(req.to_xml(), req.domain, req.username,
                       req.user_id)
    case = RequisitionCase.get(req.id)
    case.location_id = product_stock_case.location_id
    case.location_ = product_stock_case.location_
    return case


def should_notify_user(user, next_action_type):
    return user.user_data.get(UserRequisitionRoles.get_user_role(next_action_type), False)


def get_notification_recipients(next_action, requisition):
    # given a status and list of requisitions, get the exhaustive list of
    # people to notify about the requisition entering that status.
    users = get_owning_users(get_owner_id(requisition))
    if len(users) == 1:
        return users
    return [u for u in users if should_notify_user(u, next_action.action_type)]


def get_notification_message(next_action, requisitions):
    # NOTE: it'd be weird if this was None but for now we won't fail hard
    guessed_location = requisitions[0].get_location()
    summary = ', '.join(r.sms_format() for r in requisitions)
    requester = requisitions[0].get_requester()
    return notification_template(next_action.action).format(
        name=requester.full_name if requester else "Unknown",
        summary=summary,
        loc=guessed_location.site_code if guessed_location else "<loc code>",
        keyword=next_action.keyword,
    )
