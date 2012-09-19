#source, from django-tracking


from django.conf import settings
import re

# threadlocals middleware for global usage
# if this is used elsewhere in your system, consider using that instead of this.

try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local

_thread_locals = local()
def get_current_user():
    return getattr(_thread_locals, 'user', None)

class ThreadLocals(object):
    """Middleware that gets various objects from the
    request object and saves them in thread local storage."""
    def process_request(self, request):
        _thread_locals.user = getattr(request, 'user', None)



# this is not intended to be an all-knowing IP address regex
IP_RE = re.compile('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

def get_ip(request):
    """
    Retrieves the remote IP address from the request data.  If the user is
    behind a proxy, they may have a comma-separated list of IP addresses, so
    we need to account for that.  In such a case, only the first IP in the
    list will be retrieved.  Also, some hosts that use a proxy will put the
    REMOTE_ADDR into HTTP_X_FORWARDED_FOR.  This will handle pulling back the
    IP from the proper place.
    """

    # if neither header contain a value, just use local loopback
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
    if ip_address:
        # make sure we have one and only one IP
        try:
            ip_address = IP_RE.match(ip_address)
            if ip_address:
                ip_address = ip_address.group(0)
            else:
                # no IP, probably from some dirty proxy or other device
                # throw in some bogus IP
                ip_address = '10.0.0.1'
        except IndexError:
            pass
    return ip_address


#source:
# http://stackoverflow.com/questions/715234/python-dict-update-diff

def dict_diff(current, prev):
    """Return differences from dictionaries a to b.

    Return a tuple of three dicts: (removed, added, changed).
    'removed' has all keys and values removed from a. 'added' has
    all keys and values that were added to b. 'changed' has all
    keys and their values in b that are different from the corresponding
    key in a.


    modified due to added/removed reversal assumptions, now assuming current and previous are what they are.

    Goal is to have added/removed be accurate and the changed be the PREVIOUS values in prev that are changed and reflected in current.

    returns:
    tuple of (added, removed, changed)

    where

    Added:  fields:values not in prev now in current
    Removed: field:values not in current that were in prev
    Changed: field:values that changed from prev to current, and returning prev's values
    """

    removed = dict()
    added = dict()
    changed = dict()

    for key, value in current.iteritems():
        if key not in prev:
            removed[key] = value
        elif prev[key] != value:
            changed[key] = prev[key]
    for key, value in prev.iteritems():
        if key not in current:
            added[key] = value
    return added, removed, changed



#
#def get_timeout():
#    """
#    gets any specified timeout from the settings file, or use 10 minutes by
#    default
#    """
#    return getattr(settings, 'TRACKING_TIMEOUT', 10)
#
#def get_cleanup_timeout():
#    """
#    gets any specified visitor clean-up timeout from the settings file, or
#    use 24 hours by default
#    """
#    return getattr(settings, 'TRACKING_CLEANUP_TIMEOUT', 24)
#
#def get_untracked_prefixes():
#    """
#    gets a list of prefixes that shouldn't be tracked
#    """
#    return getattr(settings, 'NO_TRACKING_PREFIXES', [])
