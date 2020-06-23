#source, from django-tracking


from django.conf import settings


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

    for key, value in current.items():
        if key not in prev:
            removed[key] = value
        elif prev[key] != value:
            changed[key] = prev[key]
    for key, value in prev.items():
        if key not in current:
            added[key] = value
    return added, removed, changed


DEFAULT_TEMPLATE = "auditcare/auditcare_config_broken.html"


def login_template():
    return getattr(settings, 'LOGIN_TEMPLATE', DEFAULT_TEMPLATE)


def logout_template():
    return getattr(settings, 'LOGGEDOUT_TEMPLATE', DEFAULT_TEMPLATE)
