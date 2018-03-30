from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

COMMTRACK_USERNAME = 'commtrack-system'

COMMTRACK_SUPPLY_POINT_XMLNS = 'http://commtrack.org/supply_point'

META_XMLNS = 'http://openrosa.org/jr/xforms'

SMS_XMLNS = 'http://commtrack.org/sms_submission'


MOBILE_WORKER_UUID_NS = uuid.UUID(uuid.uuid5(uuid.NAMESPACE_URL, 'www.commcarehq.org/mobile_worker').hex)


def is_supply_point_form(form):
    return form.xmlns == COMMTRACK_SUPPLY_POINT_XMLNS


SUPPLY_POINT_CASE_TYPE = 'supply-point'
REQUISITION_CASE_TYPE = 'commtrack-requisition'  # legacy case type
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


def get_commtrack_user_id(domain):
    # abstracted out in case we one day want to back this
    # by a real user, but for now it's like demo_user
    return COMMTRACK_USERNAME

USER_LOCATION_OWNER_MAP_TYPE = 'user-owner-mapping-case'

