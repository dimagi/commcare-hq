from collections import namedtuple
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.users.signals import clean_commcare_user


def user_save_callback(sender, domain, user, forms, **kwargs):
    if (not toggles.ENIKSHAY.enabled(domain)
            or not user.is_commcare_user()):
        return

    user_form = forms.get('UpdateCommCareUserInfoForm')
    custom_data = forms.get('CustomDataEditor')
    if not user_form and custom_data:
        raise AssertionError("Expected user form and custom data form to be submitted")

    usertype = (custom_data.form.cleaned_data['usertype'][0]
                if custom_data.form.cleaned_data['usertype'] else None)

    validate_usertype(domain, user, usertype, custom_data)


def get_allowable_usertypes(domain, user):
    """Restrict choices for custom user data role field based on the chosen
    location's type"""
    location = user.get_sql_location(domain)
    if not location:
        return []
    loc_type = location.location_type.code
    return [
        ut.user_type for ut in USER_TYPES
        if ut.location_type == loc_type
    ]


def validate_usertype(domain, user, usertype, custom_data):
    """Restrict choices for custom user data role field based on the chosen
    location's type"""
    allowable_usertypes = get_allowable_usertypes(domain, user)
    if usertype not in allowable_usertypes:
        msg = _("'User Type' must be one of the following: {}").format(', '.join(allowable_usertypes))
        custom_data.form.add_error('usertype', msg)


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


def get_user_data_role(domain, user):
    """Auto-assign mobile workers a role based on a custom user data field"""


def validate_role_unchanged(domain, user):
    """Web user role is not editable"""


def get_user_data_code(domain, user):
    """Add a mobile worker code (custom user data) that's unique across all
    users at that location"""


def validate_has_location(domain, user):
    """Force a location to be chosen"""


def validate_location_unchanged(domain, user):
    """Block location reassignment on subsequent edits"""


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
