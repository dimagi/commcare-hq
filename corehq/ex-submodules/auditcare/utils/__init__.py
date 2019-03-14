#source, from django-tracking


from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
import re
import six

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
IP_RE = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')


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

    for key, value in six.iteritems(current):
        if key not in prev:
            removed[key] = value
        elif prev[key] != value:
            changed[key] = prev[key]
    for key, value in six.iteritems(prev):
        if key not in current:
            added[key] = value
    return added, removed, changed


DEFAULT_TEMPLATE = "auditcare/auditcare_config_broken.html"


def login_template():
    return getattr(settings, 'LOGIN_TEMPLATE', DEFAULT_TEMPLATE)


def logout_template():
    return getattr(settings, 'LOGGEDOUT_TEMPLATE', DEFAULT_TEMPLATE)
