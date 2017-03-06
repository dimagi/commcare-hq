from collections import namedtuple
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.users.signals import clean_commcare_user


def user_save_callback(sender, domain, user, forms, **kwargs):
    if not toggles.ENIKSHAY.enabled(domain):
        return

    new_user_form = forms.get('NewMobileWorkerForm')
    update_user_form = forms.get('UpdateCommCareUserInfoForm')
    custom_data = forms.get('CustomDataEditor')
    location_form = forms.get('CommtrackUserForm')

    if update_user_form or new_user_form:
        if not custom_data:
            raise AssertionError("Expected user form and custom data form to be submitted together")
        usertype = custom_data.form.cleaned_data['usertype']
        if new_user_form:
            location = validate_location(domain, new_user_form)
            # set_user_role(domain, user, usertype, update_user_form)
        else:
            location = user.get_sql_location(domain)
            validate_usertype(domain, location, usertype, custom_data)
            validate_role_unchanged(domain, user, update_user_form)

    if location_form:
        location_form.add_error('assigned_locations', _("You cannot edit the location of existing users."))


def get_allowable_usertypes(domain, location):
    """Restrict choices for custom user data role field based on the chosen
    location's type"""
    if not location:
        return []
    loc_type = location.location_type.code
    return [
        ut.user_type for ut in USER_TYPES
        if ut.location_type == loc_type
    ]


def validate_usertype(domain, location, usertype, custom_data):
    """Restrict choices for custom user data role field based on the chosen
    location's type"""
    allowable_usertypes = get_allowable_usertypes(domain, location)
    if usertype not in allowable_usertypes:
        msg = _("'User Type' must be one of the following: {}").format(', '.join(allowable_usertypes))
        custom_data.form.add_error('usertype', msg)


def set_user_role(domain, user, usertype, user_form):
    """Auto-assign mobile workers a role based on usertype"""
    from corehq.apps.users.models import UserRole
    roles = UserRole.by_domain_and_name(domain, usertype)
    if len(roles) == 0:
        msg = _("There is no role called '{}', you cannot create this user "
                "until that role is created.").format(usertype)
        user_form.add_error(None, msg)
    elif len(roles) > 1:
        msg = _("There are more than one roles called '{}', please delete or "
                "rename one.").format(usertype)
        user_form.add_error(None, msg)
    else:
        role = roles[0]
        user.set_role(domain, role.get_qualified_id())


def get_user_data_code(domain, user):
    """Add a mobile worker code (custom user data) that's unique across all
    users at that location"""


def validate_role_unchanged(domain, user, user_form):
    """Web user role is not editable"""
    existing_role = user.get_domain_membership(domain).role
    existing_role_id = existing_role.get_qualified_id()
    specified_role_id = user_form.cleaned_data['role']
    if existing_role_id != specified_role_id:
        msg = _("You cannot modify the user's role.  It must be {}").format(existing_role.name)
        user_form.add_error('role', msg)


def validate_location(domain, user_form):
    """Force a location to be chosen"""
    from corehq.apps.locations.models import SQLLocation
    location_id = user_form.cleaned_data['location_id']
    if location_id:
        try:
            return SQLLocation.active_objects.get(
                domain=domain, location_id=location_id)
        except SQLLocation.DoesNotExist:
            pass
    user_form.add_error('location_id', _("You must select a location."))


def connect_signals():
    clean_commcare_user.connect(user_save_callback, dispatch_uid="user_save_callback")


reports = "View All Phase 1 Reports"
mgmt_reports = "Edit Mobile Workers, View All Phase 1 Reports"

UserType = namedtuple("UserType", "user_type location_type role")

USER_TYPES = [
    UserType('to', 'phi', reports),
    UserType('tbhv', 'phi', reports),
    UserType('sts', 'tu', mgmt_reports),
    UserType('stls', 'tu', reports),
    UserType('lt-dmc', 'dmc', reports),
    UserType('lt-cdst', 'cdst', reports),
    UserType('dto', 'dto', mgmt_reports),
    UserType('deo', 'dto', mgmt_reports),
    UserType('cto', 'cto', reports),
    UserType('sto', 'sto', mgmt_reports),
    # TODO this one has loc type listed as "dto + drtb-hiv"
    # User must be assigned to both loc types, with dto as primary"
    UserType('drtb-hiv', 'drtb-hiv', reports),

    # The following user types are not in 1.0
    # UserType('mo-phi', 'phi', 'N/A'),
    # UserType('microbiologist', 'TBD', 'N/A'),
    # UserType('mo-drtb', 'TBD', 'N/A'),
    # UserType('sa', 'TBD', 'N/A'),
]


def get_site_code(domain, location):
    """Autogenerate site_code based on custom location data nikshay code and
    the codes of the ancestor locations."""


def validate_nikshay_code(domain, location):
    """When locations are created, enforce that a custom location data field
    (Nikshay code) is unique amongst sibling locations"""
    if 'nikshay_code' not in location.metadata:
        return False
    sibling_codes = [
        loc.metadata.get('nikshay_code', None)
        for loc in location.get_siblings(include_self=False)
    ]
    return location.metadata['nikshay_code'] not in sibling_codes


def validate_nikshay_code_unchanged(domain, location):
    """Block edit of custom location data nikshay code after creation"""
