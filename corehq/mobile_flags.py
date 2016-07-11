from collections import namedtuple


TAG_DIMAGI_ONLY = 'Dimagi Only'


MobileFlag = namedtuple('MobileFlag', 'slug label tags')


SUPERUSER = MobileFlag(
    'superuser',
    'Enable superuser-only features',
    tags=(TAG_DIMAGI_ONLY,)
)
