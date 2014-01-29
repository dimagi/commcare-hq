
COMMTRACK_USERNAME = 'commtrack-system'


COMMTRACK_SUPPLY_POINT_XMLNS = 'http://openrosa.org/commtrack/supply_point'
COMMTRACK_SUPPLY_POINT_PRODUCT_XMLNS = 'http://openrosa.org/commtrack/supply_point_product'
COMMTRACK_REPORT_XMLNS = 'http://openrosa.org/commtrack/stock_report'

def is_commtrack_form(form):
    return form.xmlns in [
        COMMTRACK_SUPPLY_POINT_XMLNS,
        COMMTRACK_SUPPLY_POINT_PRODUCT_XMLNS,
        COMMTRACK_REPORT_XMLNS,
    ]


SUPPLY_POINT_CASE_TYPE = 'supply-point'
SUPPLY_POINT_PRODUCT_CASE_TYPE = 'supply-point-product'
REQUISITION_CASE_TYPE = 'commtrack-requisition'

def is_commtrack_case(case):
    return case.type in [
        SUPPLY_POINT_CASE_TYPE,
        SUPPLY_POINT_PRODUCT_CASE_TYPE,
        REQUISITION_CASE_TYPE,
    ]

ALL_PRODUCTS_TRANSACTION_TAG = '_all_products'

# supply point products --> supply points and sp product --> requisitions
PARENT_CASE_REF = 'parent'

# http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)

RequisitionActions = enum(
    REQUEST='request',
    APPROVAL='approval',
    PACK='pack',
    RECEIPTS='requisition-receipts',
)

# feels a bit silly to duplicate this
ORDERED_REQUISITION_ACTIONS = (
    RequisitionActions.REQUEST,
    RequisitionActions.APPROVAL,
    RequisitionActions.PACK,
    RequisitionActions.RECEIPTS,
)

class UserRequisitionRoles(object):
    REQUESTER = 'commtrack_requester'
    APPROVER = 'commtrack_approver'
    SUPPLIER = 'commtrack_supplier'
    RECEIVER = 'commtrack_receiver'

    @classmethod
    def get_user_role(cls, action_type):
        return {
            RequisitionActions.REQUEST: cls.REQUESTER,
            RequisitionActions.APPROVAL: cls.APPROVER,
            RequisitionActions.PACK: cls.SUPPLIER,
            RequisitionActions.RECEIPTS: cls.RECEIVER,
        }[action_type]


class RequisitionStatus(object):
    """a const for our requisition status choices"""
    REQUESTED = "requested"
    APPROVED = "approved"
    PACKED = "packed"
    RECEIVED = "received"
    CANCELED = "canceled"
    CHOICES = [REQUESTED, APPROVED, PACKED, RECEIVED, CANCELED]
    CHOICES_PENDING = [REQUESTED, APPROVED, PACKED]
    CHOICES_CLOSED = [RECEIVED, CANCELED]

    @classmethod
    def by_action_type(cls, type):
        return {
            RequisitionActions.REQUEST: cls.REQUESTED,
            RequisitionActions.APPROVAL: cls.APPROVED,
            RequisitionActions.PACK: cls.PACKED,
            RequisitionActions.RECEIPTS: cls.RECEIVED,
        }[type]

    @classmethod
    def to_action_type(cls, status):
        return {
            cls.REQUESTED: RequisitionActions.REQUEST,
            cls.APPROVED: RequisitionActions.APPROVAL,
            cls.PACKED: RequisitionActions.PACK,
            cls.RECEIVED: RequisitionActions.RECEIPTS,
        }[status]

def get_commtrack_user_id(domain):
    # abstracted out in case we one day want to back this
    # by a real user, but for now it's like demo_user
    return COMMTRACK_USERNAME

USER_LOCATION_OWNER_MAP_TYPE = 'user-owner-mapping-case'
