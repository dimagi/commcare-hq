from collections import namedtuple
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.users.signals import clean_commcare_user
from corehq.apps.locations.signals import clean_location

TYPES_WITH_REQUIRED_NIKSHAY_CODES = ['sto', 'dto', 'tu', 'dmc', 'phi']


def clean_user_callback(sender, domain, user, forms, **kwargs):
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



def clean_location_callback(sender, domain, location, forms, **kwargs):
    if not toggles.ENIKSHAY.enabled(domain):
        return

    is_new_location = sender == 'NewLocationView'
    location_form = forms.get('LocationForm')

    if is_new_location:
        validate_nikshay_code(domain, location_form)
    else:
        validate_nikshay_code_unchanged(location, location_form)

    set_available_tests(location, location_form)
    set_site_code(location_form)


def set_site_code(location_form):
    """Autogenerate site_code based on custom location data nikshay code and
    the codes of the ancestor locations."""
    # TODO How is this supposed to work if 'nikshay_code' isn't always required?
    nikshay_code = location_form.custom_data.form.cleaned_data.get('nikshay_code') or ''
    ancestor_codes = [l.metadata.get('nikshay_code') or ''
                      for l in location_form['parent'].get_ancestors(include_self=True)]
    ancestor_codes.append(nikshay_code)
    location_form.cleaned_data['site_code'] = '-'.join(ancestor_codes)


def validate_nikshay_code(domain, location_form):
    """When locations are created, enforce that a custom location data field
    (Nikshay code) is unique amongst sibling locations"""
    from corehq.apps.locations.models import SQLLocation
    nikshay_code = location_form.custom_data.form.cleaned_data.get('nikshay_code', None)
    loctype = location_form.cleaned_data['loctype']
    if loctype not in TYPES_WITH_REQUIRED_NIKSHAY_CODES:
        return
    if not nikshay_code:
        location_form.add_error(None, "You cannot create a location without providing a nikshay_code.")
    parent = location_form.cleaned_data['parent']
    sibling_codes = [
        loc.metadata.get('nikshay_code', None)
        for loc in SQLLocation.objects.filter(domain=domain, parent=parent)
    ]
    if nikshay_code in sibling_codes:
        msg = "Nikshay Code '{}' is already in use.".format(nikshay_code)
        location_form.custom_data.form.add_error('nikshay_code', msg)


def validate_nikshay_code_unchanged(location, location_form):
    """Block edit of custom location data nikshay code after creation"""
    specified_nikshay_code = location_form.custom_data.form.cleaned_data.get('nikshay_code', None)
    existing_nikshay_code = location.metadata.get('nikshay_code', None)
    if existing_nikshay_code and specified_nikshay_code != existing_nikshay_code:
        msg = "You cannot modify the Nikshay Code of an existing location."
        location_form.custom_data.form.add_error('nikshay_code', msg)


def set_available_tests(location, location_form):
    if location_form.cleaned_data['loctype'] == 'cdst':
        # TODO find the real field name
        location.metadata['list of available tests'] = 'cbnaat'


def connect_signals():
    clean_location.connect(clean_location_callback, dispatch_uid="clean_location_callback")
    clean_commcare_user.connect(clean_user_callback, dispatch_uid="clean_user_callback")


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
