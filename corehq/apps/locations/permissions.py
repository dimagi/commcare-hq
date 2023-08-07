"""
Location Permissions
====================

Normal Access
-------------

Location Types - Users who can edit apps on the domain can edit location types.
Locations - There is an "edit_locations" and a "view_locations" permission.


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


How data is associated with locations
-------------------------------------

Restricted users only have access to their section of the hierarchy. Here's a
little about what that means conceptually, and how to implement these
restrictions.

Locations: Restricted users should be able to see and edit their own locations
and any descendants of those locations, as well as access data at those locations. See
also ``user_can_access_location_id``

Users: If a user is assigned to an accessible location, the user is also
accessible. See also ``user_can_access_other_user``

Groups: Groups are never accessible.

Forms: Forms are associated with a location via the submitting user, so if that
user is currently accessible, so is the form. Note that this means that moving
a user will affect forms even retroactively.  See also ``can_edit_form_location``

Cases: Case accessibility is determined by case owner. If the owner is a user,
then the user must be accessible for the case to be accessible. If the owner is
a location, then it must be accessible. If the owner is a case-sharing group,
the case is not accessible to any restricted users. See also
``user_can_access_case``

The ``SQLLocation`` queryset method ``accessible_to_user`` is helpful when
implementing these restrictions. Also refer to the standard reports, which do
this sort of filtering in bulk.


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
"""

from functools import wraps

from django.http import Http404
from django.utils.html import format_html
from django.utils.translation import gettext_lazy

from django_prbac.decorators import requires_privilege_raise404
from tastypie.resources import Resource

from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function

from corehq import privileges
from corehq.apps.domain.decorators import (
    login_and_domain_required,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CouchUser
from corehq.middleware import get_view_func

from .models import SQLLocation


# TODO: gettext_lazy is likely not having the desired effect, as format_html will immediately
# evaluate it against the current language.
# https://docs.djangoproject.com/en/dev/topics/i18n/translation/#other-uses-of-lazy-in-delayed-translations
# has details on how to create a delayed format_html/mark_safe


LOCATION_ACCESS_DENIED = format_html(gettext_lazy(
    "This project has restricted data access rules. Please contact your "
    "project administrator to be assigned access to data in this project. "
    'More information is available <a href="{}">here</a>.'),
    "https://wiki.commcarehq.org/display/commcarepublic/Location-Based+Data+Access+and+User+Editing+Restrictions")


LOCATION_SAFE_TASTYPIE_RESOURCES = set()

NOTIFY_EXCEPTION_MSG = (
    "Someone was just denied access to a page due to location-based "
    "access restrictions. If this happens a lot, we should investigate."
)


def locations_access_required(view_fn):
    """Decorator controlling domain-level access to locations features."""
    return (login_and_domain_required(
        requires_privilege_raise404(privileges.LOCATIONS)(view_fn)
    ))


def require_can_edit_locations(view_fn):
    """Decorator verifying that the user has permission to edit individual locations."""
    return locations_access_required(
        require_permission('edit_locations')(view_fn)
    )


def require_can_edit_or_view_locations(view_fn):
    """Decorator verifying that the user has permission to edit and view
    individual locations."""
    return locations_access_required(
        require_permission('edit_locations',
                           view_only_permission='view_locations')(view_fn)
    )


def user_can_edit_location_types(user, domain):
    return user.has_permission(domain, 'edit_apps')


def can_edit_location_types(view_fn):
    """
    Decorator controlling a user's access to a location types.
    """
    @wraps(view_fn)
    def _inner(request, domain, *args, **kwargs):
        if user_can_edit_location_types(request.couch_user, request.domain):
            return view_fn(request, domain, *args, **kwargs)
        raise Http404()
    return locations_access_required(_inner)


def can_edit_form_location(domain, web_user, form):
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
    view.is_location_safe = True

    # tastypie resources
    if isinstance(view, type) and issubclass(view, Resource):
        LOCATION_SAFE_TASTYPIE_RESOURCES.add(view.Meta.resource_name)

    return view


# Use this decorator for views that need to be marked location safe but do not actually
# apply location restrictions to the data they return e.g. case search. This is generally only applicable to endpoints
# whose client is expected to be the application engine (mobile / web apps).
location_safe_bypass = location_safe


def conditionally_location_safe(conditional_function):
    """Decorator to apply to a view function that verifies if something is location
    safe based on the arguments or kwarguments. That function should return
    True or False.

    Note - for the page to show up in the menus, the function should not rely on `request`.
    """
    def _inner(view_fn):
        view_fn._conditionally_location_safe_function = conditional_function
        return view_fn
    return _inner


def location_restricted_response(request):
    from corehq.apps.hqwebapp.views import no_permissions
    notify_exception(request, NOTIFY_EXCEPTION_MSG)
    return no_permissions(request, message=LOCATION_ACCESS_DENIED)


def location_restricted_exception(request):
    from corehq.apps.hqwebapp.views import no_permissions_exception
    notify_exception(request, NOTIFY_EXCEPTION_MSG)
    return no_permissions_exception(request, message=LOCATION_ACCESS_DENIED)


def _view_obj_is_safe(obj, request, *view_args, **view_kwargs):
    if getattr(obj, 'is_location_safe', False):
        return True
    conditional_fn = getattr(obj, '_conditionally_location_safe_function', None)
    if conditional_fn:
        return conditional_fn(obj, request, *view_args, **view_kwargs)
    return False


def is_location_safe(view_fn, request, view_args, view_kwargs):
    """
    Check if view_fn had the @location_safe decorator applied.
    request, view_args and kwargs are also needed because view_fn alone doesn't always
    contain enough information
    """
    # Tastypie
    if 'resource_name' in view_kwargs:
        return view_kwargs['resource_name'] in LOCATION_SAFE_TASTYPIE_RESOURCES

    view_func = get_view_func(view_fn, view_kwargs)
    return _view_obj_is_safe(view_func, request, *view_args, **view_kwargs)


def report_class_is_location_safe(report_class):
    cls = to_function(report_class)
    return cls and getattr(cls, 'is_location_safe', False)


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


def user_can_access_case(domain, user, case, es_case=False):
    from corehq.apps.reports.standard.cases.data_sources import CaseDisplaySQL, CaseDisplayES
    if user.has_permission(domain, 'access_all_locations'):
        return True

    if es_case:
        info = CaseDisplayES(case)
    else:
        info = CaseDisplaySQL(case)

    if info.owner_type == 'location':
        return user_can_access_location_id(domain, user, info.owner_id)
    elif info.owner_type == 'user':
        owning_user = CouchUser.get_by_user_id(info.owner_id)
        return user_can_access_other_user(domain, user, owning_user)
    else:
        return False


def can_edit_location(view_fn):
    """
    Decorator controlling a user's access to a specific location.
    The decorated function must be passed a loc_id arg (eg: from urls.py)
    """
    @wraps(view_fn)
    def _inner(request, domain, loc_id, *args, **kwargs):
        if user_can_access_location_id(domain, request.couch_user, loc_id):
            return view_fn(request, domain, loc_id, *args, **kwargs)
        return location_restricted_response(request)

    return require_can_edit_locations(_inner)


def can_edit_or_view_location(view_fn):
    """
    Decorator controlling a user's access to edit or VIEW a specific location.
    The decorated function must be passed a loc_id arg (eg: from urls.py)
    """
    @wraps(view_fn)
    def _inner(request, domain, loc_id, *args, **kwargs):
        if user_can_access_location_id(domain, request.couch_user, loc_id):
            return view_fn(request, domain, loc_id, *args, **kwargs)
        return location_restricted_response(request)

    return require_can_edit_or_view_locations(_inner)
