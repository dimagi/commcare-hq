import uuid

COMMTRACK_USERNAME = 'commtrack-system'

COMMTRACK_SUPPLY_POINT_XMLNS = 'http://commtrack.org/supply_point'

META_XMLNS = 'http://openrosa.org/jr/xforms'

MOBILE_WORKER_UUID_NS = uuid.UUID(
    uuid.uuid5(
        uuid.NAMESPACE_URL,
        'www.commcarehq.org/mobile_worker'
    ).hex
)

SUPPLY_POINT_CASE_TYPE = 'supply-point'

DAYS_IN_MONTH = 30.0


# http://stackoverflow.com/questions/36932/whats-the-best-way-to-implement-an-enum-in-python
def enum(**enums):
    return type('Enum', (), enums)


StockActions = enum(
    STOCKONHAND='stockonhand',
    STOCKOUT='stockout',
    RECEIPTS='receipts',
    CONSUMPTION='consumption',
)


def get_commtrack_user_id(domain):
    # abstracted out in case we one day want to back this
    # by a real user, but for now it's like demo_user
    return COMMTRACK_USERNAME


USER_LOCATION_OWNER_MAP_TYPE = 'user-owner-mapping-case'
