from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _


class LocationAccessMiddleware(object):
    """
    Many large projects want to restrict data access by location.
    Views which handle that properly are called "location safe". This
    middleware blocks access to any non location safe features by users who
    have such a restriction.
    """

    def process_view(self, request, view_fn, view_args, view_kwargs):
        user = getattr(request, 'couch_user', None)
        if not user:
            return
        if restricted_by_location(user) and view_fn not in LOCATION_SAFE_VIEWS:
            raise PermissionDenied()


def restricted_by_location(user):
    return False  # TODO turn on


# This is a list of views which will safely restrict access based on the web
# user's assigned location where appropriate.
LOCATION_SAFE_VIEWS = (
)
