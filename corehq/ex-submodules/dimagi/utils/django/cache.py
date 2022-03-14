import hashlib
from urllib.parse import quote


def make_template_fragment_key(fragment_name, vary_on):
    # Build a unicode key for this fragment and all vary-on's.
    args = hashlib.md5(':'.join([quote(str(var)) for var in vary_on]).encode('utf-8'))
    cache_key = 'template.cache.%s.%s' % (fragment_name, args.hexdigest())
    return cache_key
