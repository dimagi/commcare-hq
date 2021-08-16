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
                "program": {
                    "set_program": {"id": program.get_id, "name": program.name}
                }
            }
        else:
            change_message = {
                "program": {
                    "clear_program": {}
                }
            }
        return change_message

    @staticmethod
    def role_change(user_role):
        if user_role:
            change_message = {
                "role": {
                    "set_role": {"id": user_role.get_qualified_id(), "name": user_role.name}
                }
            }
        else:
            change_message = {
                "role": {
                    "clear_role": {}
                }
            }
        return change_message

    @staticmethod
    def domain_removal(domain):
        return {
            "domain": {
                "remove_from_domain": {"domain": domain}
            }
        }

    # ToDo: combine this method with the 2 following for two_factor reset
    @staticmethod
    def registered_devices_reset():
        return {
            "devices": {
                "reset_devices": {}
            }
        }

    @staticmethod
    def two_factor_disabled_for_days(days):
        return {
            "two_factor": {
                "disable_for_days": {"days": days}
            }
        }

    @staticmethod
    def two_factor_disabled_with_verification(verified_by, verification_mode):
        return {
            "two_factor": {
                "disable_with_verification": {
                    "verified_by": verified_by,
                    "verification_mode": verification_mode
                }
            }
        }

    @staticmethod
    def password_reset():
        return {
            "password": {
                "reset_password": {}
            }
        }

    @staticmethod
    def status_update(active, reason):
        slug = "activate_user" if active else "deactivate_user"
        return {
            "status": {
                slug: {
                    "reason": reason
                }
            }
        }

    @staticmethod
    def phone_numbers_added(phone_numbers):
        return {
            "phone_numbers": {
                "add_phone_numbers": {
                    "phone_numbers": phone_numbers
                }
            }
        }

    @staticmethod
    def phone_numbers_removed(phone_numbers):
        return {
            "phone_numbers": {
                "remove_phone_numbers": {
                    "phone_numbers": phone_numbers
                }
            }
        }

    @staticmethod
    def profile_info(profile_id, profile_name=None):
        if profile_id:
            change_message = {
                "profile": {
                    "set_profile": {"id": profile_id, "name": profile_name}
                }
            }
        else:
            change_message = {
                "profile": {
                    "clear_profile": {}
                }
            }
        return change_message

    @staticmethod
    def primary_location_removed():
        return {
            "location": {
                "clear_primary_location": {}
            }
        }

    @staticmethod
    def primary_location_info(location):
        if location:
            change_message = {
                "location": {
                    "set_primary_location": {"id": location.location_id, "name": location.name}
                }
            }
        else:
            change_message = {
                "location": {
                    "clear_primary_location": {}
                }
            }
        return change_message

    @staticmethod
    def assigned_locations_info(locations):
        if locations:
            change_message = {
                "assigned_locations": {
                    "set_assigned_locations": {
                        "locations": [{'id': loc.location_id, 'name': loc.name} for loc in locations]
                    }
                }
            }
        else:
            change_message = {
                "assigned_locations": {
                    "clear_assigned_locations": {}
                }
            }
        return change_message

    @staticmethod
    def groups_info(groups):
        if groups:
            change_message = {
                "groups": {
                    "set_groups": {
                        "groups": [{'id': group.get_id, 'name': group.name} for group in groups]
                    }
                }
            }
        else:
            change_message = {
                "groups": {
                    "clear_groups": {}
                }
            }
        return change_message

    @staticmethod
    def added_as_web_user(domain):
        return {
            "domain": {
                "add_as_web_user": {"domain": domain}
            }
        }

    @staticmethod
    def invited_to_domain(domain):
        return {
            "domain_invitation": {
                "add_domain_invitation": {"domain": domain}
            }
        }

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return {
            "domain_invitation": {
                "remove_domain_invitation": {"domain": domain}
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


MESSAGES = {
    "set_program": UserChangeFormatter.simple_formatter(noop("Program: {name}[{id}]")),
    "clear_program": UserChangeFormatter.simple_formatter(noop("Program: None")),
    "set_role": UserChangeFormatter.simple_formatter(noop("Role: {name}[{id}]")),
    "clear_role": UserChangeFormatter.simple_formatter(noop("Role: None")),
    "remove_from_domain": UserChangeFormatter.simple_formatter(noop("Removed from domain '{domain}'")),
    "add_as_web_user": UserChangeFormatter.simple_formatter(noop("Added as web user to domain '{domain}'")),
    "reset_devices": UserChangeFormatter.simple_formatter(noop("Registered devices reset")),
    "disable_for_days": UserChangeFormatter.simple_formatter(noop("Disabled for {days} days")),
    "disable_with_verification": UserChangeFormatter.simple_formatter(
        noop('Two factor disabled. Verified by: {verified_by}, verification mode: "{verification_mode}"')
    ),
    "reset_password": UserChangeFormatter.simple_formatter(noop("Password reset")),
    "activate_user": UserChangeFormatter.simple_formatter(noop('User re-enabled. Reason: "{reason}"')),
    "deactivate_user": UserChangeFormatter.simple_formatter(noop('User disabled. Reason: "{reason}"')),
    "add_phone_numbers": UserChangeFormatter.phone_numbers_formatter(
        noop('Added phone number(s) {phone_numbers}')
    ),
    "remove_phone_numbers": UserChangeFormatter.phone_numbers_formatter(
        noop('Removed phone number(s) {phone_numbers}')
    ),
    "set_profile": UserChangeFormatter.simple_formatter(noop("Profile: {name}[{id}]")),
    "clear_profile": UserChangeFormatter.simple_formatter(noop("Profile: None")),
    "set_primary_location": UserChangeFormatter.simple_formatter(noop("Primary location: {name}[{id}]")),
    "clear_primary_location": UserChangeFormatter.simple_formatter(noop("Primary location: None")),
    "set_assigned_locations": UserChangeFormatter.assigned_locations_formatter(
        noop("Assigned locations: {locations_info}")
    ),
    "clear_assigned_locations": UserChangeFormatter.simple_formatter(noop("Assigned locations: []")),
    "set_groups": UserChangeFormatter.assigned_groups_formatter(noop("Groups: {groups_info}")),
    "clear_groups": UserChangeFormatter.simple_formatter(noop("Groups: []")),
    "add_domain_invitation": UserChangeFormatter.simple_formatter(noop("Invited to domain '{domain}'")),
    "remove_domain_invitation": UserChangeFormatter.simple_formatter(
        noop("Invitation revoked for domain '{domain}'")
    )
}


def get_messages(change_messages):
    for field_name, changes in change_messages.items():
        for slug, params in changes.items():
            yield MESSAGES[slug](params)
