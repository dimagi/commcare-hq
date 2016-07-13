from collections import namedtuple


MobileFlag = namedtuple('MobileFlag', 'slug label')


SUPERUSER = MobileFlag(
    'superuser',
    'Enable superuser-only features'
)
