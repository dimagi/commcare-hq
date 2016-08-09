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
        domain = getattr(request, 'domain', None)
        if (
            user and domain
            and not user.has_permission(domain, 'access_all_locations')
            and not is_location_safe(view_fn)
        ):
            raise PermissionDenied()


def is_location_safe(view_fn):
    def get_path(fn):
        return fn.__module__ + fn.__name__
    return get_path(view_fn) in [
        get_path(view) for view in LOCATION_SAFE_VIEWS
    ]


# This is a list of views which will safely restrict access based on the web
# user's assigned location where appropriate.
LOCATION_SAFE_VIEWS = (
)
