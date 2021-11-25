from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop as noop


class UserChangeMessage(object):
    """
    Each change message to follow the structure
    {
        "field": {
            "slug": params, # params for the message
        }
    }
    field: could be domain, phone_numbers etc as the top-level key to make them searchable
    slug: any slug in MESSAGES
    params: (optional) params for the message
    """
    @staticmethod
    def program_change(program):
        if program:
            change_message = {
                PROGRAM_FIELD: {
                    SET_PROGRAM: {"id": program.get_id, "name": program.name}
                }
            }
        else:
            change_message = {
                PROGRAM_FIELD: {
                    CLEAR_PROGRAM: {}
                }
            }
        return change_message

    @staticmethod
    def role_change(user_role):
        if user_role:
            change_message = {
                ROLE_FIELD: {
                    SET_ROLE: {"id": user_role.get_qualified_id(), "name": user_role.name}
                }
            }
        else:
            change_message = {
                ROLE_FIELD: {
                    CLEAR_ROLE: {}
                }
            }
        return change_message

    @staticmethod
    def domain_removal(domain):
        return {
            DOMAIN_FIELD: {
                REMOVE_FROM_DOMAIN: {"domain": domain}
            }
        }

    @staticmethod
    def domain_addition(domain):
        return {
            DOMAIN_FIELD: {
                ADD_TO_DOMAIN: {"domain": domain}
            }
        }

    @staticmethod
    def two_factor_disabled_with_verification(verified_by, verification_mode, disable_for_days):
        change_message = {
            TWO_FACTOR_FIELD: {
                DISABLE_WITH_VERIFICATION: {
                    "verified_by": verified_by,
                    "verification_mode": verification_mode,
                }
            }
        }
        if disable_for_days:
            change_message[TWO_FACTOR_FIELD].update({DISABLE_FOR_DAYS: {"days": disable_for_days}})
        return change_message

    @staticmethod
    def password_reset():
        return {
            PASSWORD_FIELD: {
                RESET_PASSWORD: {}
            }
        }

    @staticmethod
    def status_update(active, reason):
        slug = ACTIVATE_USER if active else DEACTIVATE_USER
        return {
            STATUS_FIELD: {
                slug: {
                    "reason": reason
                }
            }
        }

    @staticmethod
    def phone_numbers_updated(added=None, removed=None):
        change_messages = {}
        if added:
            change_messages[ADD_PHONE_NUMBERS] = {"phone_numbers": added}
        if removed:
            change_messages[REMOVE_PHONE_NUMBERS] = {"phone_numbers": removed}
        if change_messages:
            return {
                PHONE_NUMBERS_FIELD: change_messages
            }
        return {}

    @staticmethod
    def profile_info(profile_id, profile_name=None):
        if profile_id:
            change_message = {
                PROFILE_FIELD: {
                    SET_PROFILE: {"id": profile_id, "name": profile_name}
                }
            }
        else:
            change_message = {
                PROFILE_FIELD: {
                    CLEAR_PROFILE: {}
                }
            }
        return change_message

    @staticmethod
    def primary_location_removed():
        return {
            LOCATION_FIELD: {
                CLEAR_PRIMARY_LOCATION: {}
            }
        }

    @staticmethod
    def primary_location_info(location):
        if location:
            change_message = {
                LOCATION_FIELD: {
                    SET_PRIMARY_LOCATION: {"id": location.location_id, "name": location.name}
                }
            }
        else:
            change_message = {
                LOCATION_FIELD: {
                    CLEAR_PRIMARY_LOCATION: {}
                }
            }
        return change_message

    @staticmethod
    def assigned_locations_info(locations):
        if locations:
            change_message = {
                ASSIGNED_LOCATIONS_FIELD: {
                    SET_ASSIGNED_LOCATIONS: {
                        "locations": [{'id': loc.location_id, 'name': loc.name} for loc in locations]
                    }
                }
            }
        else:
            change_message = {
                ASSIGNED_LOCATIONS_FIELD: {
                    CLEAR_ASSIGNED_LOCATIONS: {}
                }
            }
        return change_message

    @staticmethod
    def groups_info(groups):
        if groups:
            change_message = {
                GROUPS_FIELD: {
                    SET_GROUPS: {
                        "groups": [{'id': group.get_id, 'name': group.name} for group in groups]
                    }
                }
            }
        else:
            change_message = {
                GROUPS_FIELD: {
                    CLEAR_GROUPS: {}
                }
            }
        return change_message

    @staticmethod
    def added_as_web_user(domain):
        return {
            DOMAIN_FIELD: {
                ADD_AS_WEB_USER: {"domain": domain}
            }
        }

    @staticmethod
    def invited_to_domain(domain):
        return {
            DOMAIN_INVITATION_FIELD: {
                ADD_DOMAIN_INVITATION: {"domain": domain}
            }
        }

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return {
            DOMAIN_INVITATION_FIELD: {
                REMOVE_DOMAIN_INVITATION: {"domain": domain}
            }
        }


class UserChangeFormatter(object):
    @staticmethod
    def simple_formatter(raw_message):
        def _formatter(params):
            return _(raw_message).format(**params)
        return _formatter

    @staticmethod
    def phone_numbers_formatter(raw_message):
        def _formatter(params):
            _params = params.copy()
            _params['phone_numbers'] = ", ".join(params['phone_numbers'])
            return _(raw_message).format(**_params)
        return _formatter

    @staticmethod
    def assigned_locations_formatter(raw_message):
        def _formatter(params):
            _params = params.copy()
            locations = _params.pop('locations')
            _params['locations_info'] = [f"{loc['name']}[{loc['id']}]" for loc in locations]
            return _(raw_message).format(**_params)
        return _formatter

    @staticmethod
    def assigned_groups_formatter(raw_message):
        def _formatter(params):
            _params = params.copy()
            groups = _params.pop('groups')
            _params['groups_info'] = [f"{group['name']}[{group['id']}]" for group in groups]
            return _(raw_message).format(**_params)
        return _formatter


# fields
PROGRAM_FIELD = "program"
ROLE_FIELD = "role"
DOMAIN_FIELD = "domain"
TWO_FACTOR_FIELD = "two_factor"
PASSWORD_FIELD = "password"
STATUS_FIELD = "status"
PHONE_NUMBERS_FIELD = "phone_numbers"
PROFILE_FIELD = "profile"
LOCATION_FIELD = "location"
ASSIGNED_LOCATIONS_FIELD = "assigned_locations"
GROUPS_FIELD = "groups"
DOMAIN_INVITATION_FIELD = "domain_invitation"

CHANGE_MESSAGES_FIELDS = [
    PROGRAM_FIELD,
    ROLE_FIELD,
    DOMAIN_FIELD,
    TWO_FACTOR_FIELD,
    PASSWORD_FIELD,
    STATUS_FIELD,
    PHONE_NUMBERS_FIELD,
    PROFILE_FIELD,
    LOCATION_FIELD,
    ASSIGNED_LOCATIONS_FIELD,
    GROUPS_FIELD,
    DOMAIN_INVITATION_FIELD,
]

# message slugs
SET_PROGRAM = 'set_program'
CLEAR_PROGRAM = 'clear_program'
SET_ROLE = 'set_role'
CLEAR_ROLE = 'clear_role'
REMOVE_FROM_DOMAIN = 'remove_from_domain'
ADD_TO_DOMAIN = 'add_to_domain'
ADD_AS_WEB_USER = 'add_as_web_user'
DISABLE_FOR_DAYS = 'disable_for_days'
DISABLE_WITH_VERIFICATION = 'disable_with_verification'
RESET_PASSWORD = 'reset_password'
ACTIVATE_USER = 'activate_user'
DEACTIVATE_USER = 'deactivate_user'
ADD_PHONE_NUMBERS = 'add_phone_numbers'
REMOVE_PHONE_NUMBERS = 'remove_phone_numbers'
SET_PROFILE = 'set_profile'
CLEAR_PROFILE = 'clear_profile'
SET_PRIMARY_LOCATION = 'set_primary_location'
CLEAR_PRIMARY_LOCATION = 'clear_primary_location'
SET_ASSIGNED_LOCATIONS = 'set_assigned_locations'
CLEAR_ASSIGNED_LOCATIONS = 'clear_assigned_locations'
SET_GROUPS = 'set_groups'
CLEAR_GROUPS = 'clear_groups'
ADD_DOMAIN_INVITATION = 'add_domain_invitation'
REMOVE_DOMAIN_INVITATION = 'remove_domain_invitation'

MESSAGES = {
    SET_PROGRAM: UserChangeFormatter.simple_formatter(noop("Program: {name}[{id}]")),
    CLEAR_PROGRAM: UserChangeFormatter.simple_formatter(noop("Program: None")),
    SET_ROLE: UserChangeFormatter.simple_formatter(noop("Role: {name}[{id}]")),
    CLEAR_ROLE: UserChangeFormatter.simple_formatter(noop("Role: None")),
    REMOVE_FROM_DOMAIN: UserChangeFormatter.simple_formatter(noop("Removed from domain '{domain}'")),
    ADD_TO_DOMAIN: UserChangeFormatter.simple_formatter(noop("Added to domain '{domain}'")),
    ADD_AS_WEB_USER: UserChangeFormatter.simple_formatter(noop("Added as web user to domain '{domain}'")),
    DISABLE_FOR_DAYS: UserChangeFormatter.simple_formatter(noop("Disabled for {days} days")),
    DISABLE_WITH_VERIFICATION: UserChangeFormatter.simple_formatter(
        noop('Two factor removed. Verified by: {verified_by}, verification mode: "{verification_mode}"')
    ),
    RESET_PASSWORD: UserChangeFormatter.simple_formatter(noop("Password reset")),
    ACTIVATE_USER: UserChangeFormatter.simple_formatter(noop('User re-enabled. Reason: "{reason}"')),
    DEACTIVATE_USER: UserChangeFormatter.simple_formatter(noop('User disabled. Reason: "{reason}"')),
    ADD_PHONE_NUMBERS: UserChangeFormatter.phone_numbers_formatter(
        noop('Added phone number(s) {phone_numbers}')
    ),
    REMOVE_PHONE_NUMBERS: UserChangeFormatter.phone_numbers_formatter(
        noop('Removed phone number(s) {phone_numbers}')
    ),
    SET_PROFILE: UserChangeFormatter.simple_formatter(noop("Profile: {name}[{id}]")),
    CLEAR_PROFILE: UserChangeFormatter.simple_formatter(noop("Profile: None")),
    SET_PRIMARY_LOCATION: UserChangeFormatter.simple_formatter(noop("Primary location: {name}[{id}]")),
    CLEAR_PRIMARY_LOCATION: UserChangeFormatter.simple_formatter(noop("Primary location: None")),
    SET_ASSIGNED_LOCATIONS: UserChangeFormatter.assigned_locations_formatter(
        noop("Assigned locations: {locations_info}")
    ),
    CLEAR_ASSIGNED_LOCATIONS: UserChangeFormatter.simple_formatter(noop("Assigned locations: []")),
    SET_GROUPS: UserChangeFormatter.assigned_groups_formatter(noop("Groups: {groups_info}")),
    CLEAR_GROUPS: UserChangeFormatter.simple_formatter(noop("Groups: []")),
    ADD_DOMAIN_INVITATION: UserChangeFormatter.simple_formatter(noop("Invited to domain '{domain}'")),
    REMOVE_DOMAIN_INVITATION: UserChangeFormatter.simple_formatter(
        noop("Invitation revoked for domain '{domain}'")
    )
}


def get_messages(change_messages):
    for field_name, changes in change_messages.items():
        for slug, params in changes.items():
            yield MESSAGES[slug](params)
