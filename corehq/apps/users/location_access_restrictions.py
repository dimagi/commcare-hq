from django.utils.translation import ugettext as _

from tastypie.resources import Resource
from corehq.apps.hqwebapp.views import no_permissions

LOCATION_SAFE_TASTYPIE_RESOURCES = set()


def location_safe(view_fn):
    view_fn.is_location_safe = True
    return view_fn


def tastypie_location_safe(resource):
    """
    tastypie is a special snowflake that doesn't preserve anything, so it gets
    it's own class decorator:

        @tastypie_location_safe
        class LocationResource(HqBaseResource):
            type = "location"
    """
    if not issubclass(resource, Resource):
        raise TypeError("This decorator can only be applied to tastypie resources")
    LOCATION_SAFE_TASTYPIE_RESOURCES.add(resource.Meta.resource_name)
    return resource


def location_restricted_response(request):
    return no_permissions(request, message=_(
        "This project has restricted data access rules.  Please contact your "
        "project administrator to access specific data in the project"
    ))


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
                not is_location_safe(view_fn, view_args, view_kwargs)
                or not user.get_sql_location(domain)
            ):
                return location_restricted_response(request)


def is_location_safe(view_fn, view_args, view_kwargs):
    """
    Check if view_fn had the @location_safe decorator applied.
    view_args and kwargs are also needed because view_fn alone doesn't always
    contain enough information
    """
    if getattr(view_fn, 'is_location_safe', False):
        return True
    if 'resource_name' in view_kwargs:
        return view_kwargs['resource_name'] in LOCATION_SAFE_TASTYPIE_RESOURCES
    return False
