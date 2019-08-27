import hashlib
from django.utils.http import urlquote


def make_template_fragment_key(fragment_name, vary_on):
    # Build a unicode key for this fragment and all vary-on's.
    args = hashlib.md5(':'.join([urlquote(var) for var in vary_on]).encode('utf-8'))
    cache_key = 'template.cache.%s.%s' % (fragment_name, args.hexdigest())
    return cache_key
