from collections import namedtuple
"""
Autogenerate some stuff when users and locations are saved
[User] Auto-assign mobile workers a role based on a custom user data field
[User] Add a mobile worker code (custom user data) that's unique across all users at that location
[Location] Autogenerate site_code based on custom location data nikshay code and the codes of the ancestor locations

Perform additional validation or modification BEFORE saving
[Location] When locations are created, enforce that a custom location data field (Nikshay code) is unique amongst sibling locations
[User] Force a location to be chosen
[User] Block location reassignment on subsequent edits
[User] Web user role is not editable
[Location] Block edit of custom location data nikshay code

Have a custom field with a fancy widget and validation
[User] Restrict choices for custom user data role field based on the chosen location's type
"""

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
    # TODO this one has loc type listed as "dto + drtb-hiv", what's that about?
    # note says that "dto location must be set as primary"
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
