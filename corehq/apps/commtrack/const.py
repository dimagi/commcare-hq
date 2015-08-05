COMMTRACK_USERNAME = 'commtrack-system'

COMMTRACK_SUPPLY_POINT_XMLNS = 'http://commtrack.org/supply_point'

META_XMLNS = 'http://openrosa.org/jr/xforms'

SMS_XMLNS = 'http://commtrack.org/sms_submission'


def is_supply_point_form(form):
    return form.xmlns == COMMTRACK_SUPPLY_POINT_XMLNS


SUPPLY_POINT_CASE_TYPE = 'supply-point'
REQUISITION_CASE_TYPE = 'commtrack-requisition'
FULFILLMENT_CASE_TYPE = 'commtrack-fulfillment'
RECEIVED_CASE_TYPE = 'commtrack-received'
ORDER_CASE_TYPE = 'commtrack-order'

DAYS_IN_MONTH = 30.0

def is_commtrack_case(case):
    return case.type in [
        SUPPLY_POINT_CASE_TYPE,
        REQUISITION_CASE_TYPE,
        FULFILLMENT_CASE_TYPE,
        ORDER_CASE_TYPE,
    ]

ALL_PRODUCTS_TRANSACTION_TAG = '_all_products'

# supply point products --> supply points and sp product --> requisitions
PARENT_CASE_REF = 'parent'

# http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)

StockActions = enum(
    STOCKONHAND='stockonhand',
    STOCKOUT='stockout',
    RECEIPTS='receipts',
    CONSUMPTION='consumption',
    LA='lossoradjustment'
)

RequisitionActions = enum(
    REQUEST='request',
    APPROVAL='approval',
    FULFILL='fulfill',
    PACK='pack',  # todo: pack and fulfill are the same thing but both are used. should reconcile
    RECEIPTS='requisition-receipts',
)

# feels a bit silly to duplicate this
ORDERED_REQUISITION_ACTIONS = (
    RequisitionActions.REQUEST,
    RequisitionActions.APPROVAL,
    RequisitionActions.FULFILL,
    RequisitionActions.PACK,
    RequisitionActions.RECEIPTS,
)

class RequisitionStatus(object):
    """a const for our requisition status choices"""
    REQUESTED = "requested"
    APPROVED = "approved"
    FULFILLED = "fulfilled"
    RECEIVED = "received"
    CANCELED = "canceled"
    CHOICES = [REQUESTED, APPROVED, FULFILLED, RECEIVED, CANCELED]
    CHOICES_PENDING = [REQUESTED, APPROVED, FULFILLED]
    CHOICES_CLOSED = [RECEIVED, CANCELED]

    @classmethod
    def by_action_type(cls, type):
        return {
            RequisitionActions.REQUEST: cls.REQUESTED,
            RequisitionActions.APPROVAL: cls.APPROVED,
            RequisitionActions.FULFILL: cls.FULFILLED,
            RequisitionActions.RECEIPTS: cls.RECEIVED,
        }[type]

    @classmethod
    def to_action_type(cls, status):
        return {
            cls.REQUESTED: RequisitionActions.REQUEST,
            cls.APPROVED: RequisitionActions.APPROVAL,
            cls.FULFILLED: RequisitionActions.FULFILL,
            cls.RECEIVED: RequisitionActions.RECEIPTS,
        }[status]

def get_commtrack_user_id(domain):
    # abstracted out in case we one day want to back this
    # by a real user, but for now it's like demo_user
    return COMMTRACK_USERNAME

USER_LOCATION_OWNER_MAP_TYPE = 'user-owner-mapping-case'

