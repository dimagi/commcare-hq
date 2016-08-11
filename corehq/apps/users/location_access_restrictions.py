from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.hqwebapp.views import no_permissions
from corehq.apps.locations import views as location_views

LOCATION_ACCESS_MSG = (
    "This project has restricted data access rules.  Please contact your "
    "project administrator to access specific data in the project"
)


class LocationAccessMiddleware(object):
    """
    Many large projects want to restrict data access by location.
    Views which handle that properly are called "location safe". This
    middleware blocks access to any non location safe features by users who
    have such a restriction. If these users do not have an assigned location,
    they cannot access anything.
    """

    def process_view(self, request, view_fn, view_args, view_kwargs):
        user = getattr(request, 'couch_user', None)
        domain = getattr(request, 'domain', None)
        if not user or not domain:
            request.can_access_all_locations = True
        elif user.has_permission(domain, 'access_all_locations'):
            request.can_access_all_locations = True
        else:
            request.can_access_all_locations = False
            if (
                not is_location_safe(view_fn)
                or not user.get_sql_location(domain)
            ):
                return no_permissions(request, message=LOCATION_ACCESS_MSG)


class ViewSafetyChecker(object):
    @property
    @memoized
    def _location_safe_views(self):
        """
        This is a set of views which will safely restrict access based on the web
        user's assigned location where appropriate. It's implemented as a
        classmethod so it can be lazily initialized (to minimize
        import loops) and memoized.
        """
        from corehq.apps.locations import views as location_views
        return {self._get_view_path(view_fn) for view_fn in (
            location_views.LocationsListView,
        )}

    @memoized
    def _is_location_safe_path(self, view_path):
        return view_path in self._location_safe_views

    def _get_view_path(self, view_fn):
        return '.'.join([view_fn.__module__, view_fn.__name__])

    def is_location_safe(self, view_fn):
        return self._is_location_safe_path(self._get_view_path(view_fn))


view_safety_checker = ViewSafetyChecker()

def is_location_safe(view_fn):
    return view_safety_checker.is_location_safe(view_fn)
