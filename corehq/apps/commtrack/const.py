
COMMTRACK_USERNAME = 'commtrack-system'

SUPPLY_POINT_CASE_TYPE = 'supply-point'
SUPPLY_POINT_PRODUCT_CASE_TYPE = 'supply-point-product'
REQUISITION_CASE_TYPE = 'commtrack-requisition'

ALL_PRODUCTS_TRANSACTION_TAG = '_all_products'

# supply point products --> supply points and sp product --> requisitions
PARENT_CASE_REF = 'parent'

# http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)

RequisitionActions = enum(
    REQUEST='request',
    APPROVAL='approval',
    FILL='fill',
    RECEIPTS='requisition-receipts',
)

class RequisitionStatus(object):
    """a const for our requisition status choices"""
    REQUESTED = "requested"
    APPROVED = "approved"
    FILLED = "filled"
    RECEIVED = "received"
    CANCELED = "canceled"
    CHOICES = [REQUESTED, APPROVED, FILLED, RECEIVED, CANCELED]
    CHOICES_PENDING = [REQUESTED, APPROVED, FILLED]
    CHOICES_CLOSED = [RECEIVED, CANCELED]

    @classmethod
    def by_action_type(cls, type):
        return {
            RequisitionActions.REQUEST: cls.REQUESTED,
            RequisitionActions.APPROVAL: cls.APPROVED,
            RequisitionActions.FILL: cls.FILLED,
            RequisitionActions.RECEIPTS: cls.RECEIVED,
        }[type]
