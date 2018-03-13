from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from django.utils.translation import ugettext as _
from corehq.apps.locations.models import SQLLocation


LocationCache = namedtuple("LocationCache", "is_error location message")


def get_memoized_location_getter(domain):
    """
    Returns a memoized location getter containing error information.
    """
    locations = {}

    def get_location(user_input):
        user_input = user_input.lower()
        if user_input not in locations:
            try:
                loc = SQLLocation.objects.get_from_user_input(domain, user_input)
                locations[user_input] = LocationCache(False, loc, None)
            except SQLLocation.DoesNotExist:
                locations[user_input] = LocationCache(True, None, _(
                    "Unknown location: '%(name)s'. But the row is "
                    "successfully added"
                ) % {'name': user_input})
            except SQLLocation.MultipleObjectsReturned:
                locations[user_input] = LocationCache(True, None, _(
                    "Multiple locations found with the name: '%(name)s'.  "
                    "Try using site code. But the row is successfully added"
                ) % {'name': user_input})
        return locations[user_input]
    return get_location
