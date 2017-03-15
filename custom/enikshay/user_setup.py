from collections import namedtuple
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.users.signals import clean_commcare_user
from corehq.apps.locations.signals import clean_location

TYPES_WITH_REQUIRED_NIKSHAY_CODES = ['sto', 'dto', 'tu', 'dmc', 'phi']
LOC_TYPES_TO_USER_TYPES = {
    'phi': ['to', 'tbhv', 'mo-phi'],
    'tu': ['sts', 'stls'],
    'dmc': ['lt-dmc'],
    'cdst': ['lt-cdst'],
    'dto': ['dto', 'deo'],
    'cto': ['cto'],
    'sto': ['sto'],
}


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

        location = (validate_location(domain, new_user_form)
                    if new_user_form else user.get_sql_location(domain))
        if not location:
            return

        usertype = custom_data.form.cleaned_data['usertype']
        validate_usertype(domain, location, usertype, custom_data)
        if new_user_form:
            set_user_role(domain, user, usertype, new_user_form)
        else:
            validate_role_unchanged(domain, user, update_user_form)

    if location_form:
        location_form.add_error('assigned_locations', _("You cannot edit the location of existing users."))


def validate_usertype(domain, location, usertype, custom_data):
    """Restrict choices for custom user data role field based on the chosen
    location's type"""
    # TODO handle multiple locations.  How are they created?
    # maybe set secondary loc to 'drtb-hiv' if usertype == 'drtb-hiv'?
    location_codes = []
    if location.location_type.code == 'dto' and 'drtb-hiv' in location_codes:
        return
    allowable_usertypes = LOC_TYPES_TO_USER_TYPES[location.location_type.code]
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
    if not existing_role:
        return
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

    location_form = forms.get('LocationForm')

    if location_form.is_new_location:
        validate_nikshay_code(domain, location_form)
    else:
        validate_nikshay_code_unchanged(location, location_form)

    set_available_tests(location, location_form)
    set_site_code(location_form)


def set_site_code(location_form):
    """Autogenerate site_code based on custom location data nikshay code and
    the codes of the ancestor locations."""
    # TODO How is this supposed to work if 'nikshay_code' isn't always required?
    # maybe use site_code?
    nikshay_code = location_form.custom_data.form.cleaned_data.get('nikshay_code') or ''
    parent = location_form.cleaned_data['parent']
    ancestors = parent.get_ancestors(include_self=True) if parent else []
    ancestor_codes = [l.metadata.get('nikshay_code') or '' for l in ancestors]
    ancestor_codes.append(nikshay_code)
    location_form.cleaned_data['site_code'] = '-'.join(ancestor_codes)


def validate_nikshay_code(domain, location_form):
    """When locations are created, enforce that a custom location data field
    (Nikshay code) is unique amongst sibling locations"""
    from corehq.apps.locations.models import SQLLocation
    nikshay_code = location_form.custom_data.form.cleaned_data.get('nikshay_code', None)
    loctype = location_form.cleaned_data['location_type']
    if loctype not in TYPES_WITH_REQUIRED_NIKSHAY_CODES:
        return
    if not nikshay_code:
        location_form.add_error(None, "You cannot create this location without providing a nikshay_code.")
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
    if location_form.cleaned_data['location_type'] == 'cdst':
        # TODO find the real field name
        location.metadata['list of available tests'] = 'cbnaat'


def connect_signals():
    clean_location.connect(clean_location_callback, dispatch_uid="clean_location_callback")
    clean_commcare_user.connect(clean_user_callback, dispatch_uid="clean_user_callback")
