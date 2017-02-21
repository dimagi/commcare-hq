"""
Location Permissions
====================

Normal Access
-------------

Location Types - Users who can edit apps on the domain can edit location types::
Locations - Users who can edit mobile workers on the domain can edit locations


Restricted Access and Whitelist
--------------------------------

Many large projects have mid-level users who should have access to a subset of
the project based on the organization's hierarchy.

This is handled by a special permission called "Full Organization Access" which
is enabled by default on all user roles. To restrict data access based on a
user's location, projects may create a user role with this permission disabled.

This is checked like so::

    user.has_permission(domain, 'access_all_locations')

We have whitelisted portions of HQ that have been made to correctly handle
these restricted users. Anything not explicitly whitelisted is inaccessible to
restricted users.


Whitelist Implementation
------------------------

There is ``LocationAccessMiddleware`` which controls this whitelist. It
intercepts every request, checks if the user has restricted access to the
domain, and if so, only allows requests to whitelisted views. This middleware
also guarantees that restricted users have a location assigned. That is, if a
user should be restricted, but does not have an assigned location, they can't
see anything. This is to prevent users from obtaining full access in the event
that their location is deleted or improperly assigned.

The other component of this is uitabs. The menu bar and the sidebar on HQ are
composed of a bunch of links and names, essentially. We run the url for each of
these links against the same check that the middleware uses to see if it should
be visible to the user. In this way, they only see menu and sidebar links that
are accessible.

To mark a view as location safe, you apply the ``@location_safe`` decorator to
it. This can be applied directly to view functions, view classes, HQ report
classes, or tastypie resources (see implentation and existing usages for
examples).

UCR and Report Builder reports will be automatically marked as location safe if
the report contains a location choice provider. This is done using the
``conditionally_location_safe`` decorator, which is provided with a function that
in this case checks that the report has at least one location choice provider.

When marking a view as location safe, you must also check for restricted users
by using either ``request.can_access_all_locations`` or
``user.has_permission(domain, 'access_all_locations')`` and limit the data
returned accordingly.

You should create a user who is restricted and click through the desired
workflow to make sure it still makes sense, there could be for instance, ajax
requests that must also be protected, or links to features the user shouldn't
see.


Legacy Implementation
---------------------
Prior to the implementation of the whitelist, we created a series of
unconnected location-based permissions schemes controlled by feature flags.
These each restrict access to a particular feature and don't affect the rest of
HQ. These are deprecated, and we intend to transition projects off of those
onto the whitelist once we've added enough features to meet their use-case.
"""
from django_prbac.decorators import requires_privilege_raise404
from tastypie.resources import Resource
from corehq import privileges
from functools import wraps
from dimagi.utils.logging import notify_exception
from django.http import Http404
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
from django.views.generic import View
from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.domain.decorators import (login_and_domain_required,
                                           domain_admin_required)
from corehq.apps.reports.generic import GenericReportView
from corehq.apps.users.models import CouchUser
from .models import SQLLocation

LOCATION_ACCESS_DENIED = mark_safe(ugettext_lazy(
    "This project has restricted data access rules. Please contact your "
    "project administrator to be assigned access to data in this project. "
    'More information is available <a href="{link}">here</a>.'
).format(link="https://wiki.commcarehq.org/display/commcarepublic/Data+Access+and+User+Editing+Restrictions"))

LOCATION_SAFE_TASTYPIE_RESOURCES = set()

LOCATION_SAFE_HQ_REPORTS = set()


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


#### Unified location permissions below this point
# TODO incorporate the above stuff into the new system


def can_edit_form_location(domain, web_user, form):
    # Domain admins can always edit locations.  If the user isn't an admin and
    # the location restriction is enabled, they can only edit forms that are
    # explicitly at or below them in the location tree.

    # This first block checks for old permissions, remove when that's gone
    if toggles.RESTRICT_FORM_EDIT_BY_LOCATION.enabled(domain):
        domain_obj = Domain.get_by_name(domain)
        if user_can_edit_any_location(web_user, domain_obj):
            return True
        if not form.user_id:
            return False
        form_user = CouchUser.get_by_user_id(form.user_id)
        if not form_user:
            # form most likely submitted by a system user
            return False
        for location in form_user.get_sql_locations(domain):
            if user_can_edit_location(web_user, location, domain_obj):
                return True
        return False

    if web_user.has_permission(domain, 'access_all_locations'):
        return True

    if not form.user_id:
        return False

    form_user = CouchUser.get_by_user_id(form.user_id)
    if not form_user:
        return False  # It's a special form, deny to be safe
    form_location_ids = form_user.get_location_ids(domain)
    return user_can_access_any_location_id(domain, web_user, form_location_ids)


def location_safe(view):
    """Decorator to apply to a view after making sure it's location-safe
    Supports view functions, class-based views, tastypie resources, and HQ reports.
    For classes, decorate the class, not the dispatch method.
    """
    # view functions
    view.is_location_safe = True

    if isinstance(view, type):  # it's a class

        # Django class-based views
        if issubclass(view, View):
            # `View.as_view()` preserves stuff set on `dispatch`
            view.dispatch.__func__.is_location_safe = True

        # tastypie resources
        if issubclass(view, Resource):
            LOCATION_SAFE_TASTYPIE_RESOURCES.add(view.Meta.resource_name)

        # HQ report classes
        if issubclass(view, GenericReportView):
            LOCATION_SAFE_HQ_REPORTS.add(view.slug)

    return view


def conditionally_location_safe(conditional_function):
    """Decorator to apply to a view function that verifies if something is location
    safe based on the arguments or kwarguments. That function should return
    True or False.

    """
    def _inner(view_fn):
        view_fn._conditionally_location_safe_function = conditional_function
        return view_fn
    return _inner


def location_restricted_response(request):
    from corehq.apps.hqwebapp.views import no_permissions
    msg = ("Someone was just denied access to a page due to location-based "
           "access restrictions. If this happens a lot, we should investigate.")
    notify_exception(request, msg)
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
    if getattr(view_fn, '_conditionally_location_safe_function', False):
        return view_fn._conditionally_location_safe_function(view_fn, *view_args, **view_kwargs)
    if getattr(view_fn, 'is_hq_report', False):
        return view_kwargs['report_slug'] in LOCATION_SAFE_HQ_REPORTS
    return False


def user_can_access_location_id(domain, user, location_id):
    if user.has_permission(domain, 'access_all_locations'):
        return True

    return (SQLLocation.objects
            .accessible_to_user(domain, user)
            .filter(location_id=location_id)
            .exists())


def user_can_access_any_location_id(domain, user, location_ids):
    if user.has_permission(domain, 'access_all_locations'):
        return True

    return (SQLLocation.objects
            .accessible_to_user(domain, user)
            .filter(location_id__in=location_ids)
            .exists())


def user_can_access_other_user(domain, user, other_user):
    if user.has_permission(domain, 'access_all_locations'):
        return True

    return (other_user
            .get_sql_locations(domain)
            .accessible_to_user(domain, user)
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
