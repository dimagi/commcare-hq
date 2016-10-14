from django_prbac.decorators import requires_privilege_raise404
from tastypie.resources import Resource
from corehq import privileges
from functools import wraps
from django.http import Http404
from django.utils.translation import ugettext_lazy
from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.domain.decorators import (login_and_domain_required,
                                           domain_admin_required)
from corehq.apps.users.models import CommCareUser
from .models import SQLLocation
from .util import get_xform_location

LOCATION_ACCESS_DENIED = ugettext_lazy(
    "This project has restricted data access rules.  Please contact your "
    "project administrator to access specific data in the project"
)

LOCATION_SAFE_TASTYPIE_RESOURCES = set()


def locations_access_required(view_fn):
    """
    Decorator controlling domain-level access to locations.
    """
    return login_and_domain_required(
        requires_privilege_raise404(privileges.LOCATIONS)(view_fn)
    )


def is_locations_admin(view_fn):
    """
    Decorator controlling write access to locations.
    """
    return locations_access_required(domain_admin_required(view_fn))


def user_can_edit_any_location(user, project):
    return user.is_domain_admin(project.name) or not project.location_restriction_for_users


def can_edit_any_location(view_fn):
    """
    Decorator determining whether a user has permission to edit all locations in a project
    """
    @wraps(view_fn)
    def _inner(request, domain, *args, **kwargs):
        if user_can_edit_any_location(request.couch_user, request.project):
            return view_fn(request, domain, *args, **kwargs)
        raise Http404()
    return locations_access_required(_inner)


def get_user_location(user, domain):
    if user.is_commcare_user():
        return user.location
    else:
        return user.get_location(domain)


def get_user_sql_location(user, domain):
    if user.is_commcare_user():
        return user.sql_location
    else:
        return user.get_sql_location(domain)


def user_can_edit_location(user, sql_location, project):
    if user_can_edit_any_location(user, project):
        return True

    user_loc = get_user_sql_location(user, sql_location.domain)
    if not user_loc:
        return False
    return user_loc.is_direct_ancestor_of(sql_location)


def user_can_view_location(user, sql_location, project):
    if (user.is_domain_admin(project.name) or
            not project.location_restriction_for_users):
        return True

    user_loc = get_user_location(user, sql_location.domain)

    if not user_loc:
        return True

    if user_can_edit_location(user, sql_location, project):
        return True

    return sql_location.location_id in user_loc.lineage


def user_can_edit_location_types(user, project):
    if user.is_domain_admin(project.name):
        return True
    elif not user.has_permission(project.name, 'edit_apps'):
        return False
    elif not project.location_restriction_for_users:
        return True

    return not user.get_domain_membership(project.name).location_id


def can_edit_location_types(view_fn):
    """
    Decorator controlling a user's access to a location types.
    """
    @wraps(view_fn)
    def _inner(request, domain, *args, **kwargs):
        if user_can_edit_location_types(request.couch_user, request.project):
            return view_fn(request, domain, *args, **kwargs)
        raise Http404()
    return locations_access_required(_inner)


def can_edit_form_location(domain, web_user, form):
    # Domain admins can always edit locations.  If the user isn't an admin and
    # the location restriction is enabled, they can only edit forms that are
    # explicitly at or below them in the location tree.
    domain_obj = Domain.get_by_name(domain)
    if (not toggles.RESTRICT_FORM_EDIT_BY_LOCATION.enabled(domain)
            or user_can_edit_any_location(web_user, domain_obj)):
        return True

    if domain_obj.supports_multiple_locations_per_user:
        user_id = form.user_id
        if not user_id:
            return False

        form_user = CommCareUser.get(user_id)
        for location in form_user.locations:
            if user_can_edit_location(web_user, location.sql_location, domain_obj):
                return True
        return False

    else:
        form_location = get_xform_location(form)
        if not form_location:
            return False
        return user_can_edit_location(web_user, form_location, domain_obj)


#### Unified location permissions below this point
# TODO incorporate the above stuff into the new system


def location_safe(view_fn):
    """Decorator to apply to a view after making sure it's location-safe"""
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
    from corehq.apps.hqwebapp.views import no_permissions
    return no_permissions(request, message=LOCATION_ACCESS_DENIED)


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


def user_can_access_location_id(domain, user, location_id):
    if user.has_permission(domain, 'access_all_locations'):
        return True

    return (SQLLocation.objects
            .accessible_to_user(domain, user)
            .filter(location_id=location_id)
            .exists())


def can_edit_location(view_fn):
    """
    Decorator controlling a user's access to a specific location.
    The decorated function must be passed a loc_id arg (eg: from urls.py)
    """
    @wraps(view_fn)
    def _inner(request, domain, loc_id, *args, **kwargs):
        if Domain.get_by_name(domain).location_restriction_for_users:
            # TODO Old style restrictions, remove after converting existing projects
            try:
                # pass to view?
                location = SQLLocation.objects.get(location_id=loc_id)
            except SQLLocation.DoesNotExist:
                raise Http404()
            else:
                if user_can_edit_location(request.couch_user, location, request.project):
                    return view_fn(request, domain, loc_id, *args, **kwargs)
            raise Http404()

        if user_can_access_location_id(domain, request.couch_user, loc_id):
            return view_fn(request, domain, loc_id, *args, **kwargs)
        return location_restricted_response(request)

    return locations_access_required(_inner)
