from django.utils.translation import ugettext_lazy
from corehq.apps.hqwebapp.views import no_permissions
from .permissions import is_location_safe, location_restricted_response

RESTRICTED_USER_UNASSIGNED_MSG = ugettext_lazy("""
Your user role allows you to access data based on your assigned location in the
organization hierarchy. You do not currently have an assigned location, and
will be unable to access CommCareHQ until that is corrected. Please contact
your project administrator to be assigned to a location.
""")


class LocationAccessMiddleware(object):
    """
    Many large projects want to restrict data access by location.
    Views which handle that properly are called "location safe". This
    middleware blocks access to any non location safe features by users who
    have such a restriction. If these users do not have an assigned location,
    they cannot access anything.

    This middleware also sets the property can_access_all_locations. This
    property does not imply domain level authentication or access to any
    particular feature. All it says is that whether or not the user has a role
    which restricts their data access by location.
    """

    def process_view(self, request, view_fn, view_args, view_kwargs):
        user = getattr(request, 'couch_user', None)
        domain = getattr(request, 'domain', None)
        if not domain or not user or not user.is_member_of(domain):
            # This is probably some non-domain page or a test, let normal auth handle it
            request.can_access_all_locations = True
        elif user.has_permission(domain, 'access_all_locations'):
            request.can_access_all_locations = True
        else:
            request.can_access_all_locations = False
            if not is_location_safe(view_fn, view_args, view_kwargs):
                return location_restricted_response(request)
            elif not user.get_sql_location(domain):
                return no_permissions(request, message=RESTRICTED_USER_UNASSIGNED_MSG)
