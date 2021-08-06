from django.utils.translation import ugettext_lazy as _, ugettext_noop as noop


MESSAGES = {
    "set_program": noop("Program: {name}[{id}]"),
    "clear_program": noop("Program: None"),
    "set_role": noop("Role: {name}[{id}]"),
    "clear_role": noop("Role: None"),
    "remove_from_domain": noop("Removed from domain '{domain}'"),
    "add_as_web_user": noop("Added as web user to domain '{domain}'"),
    "reset_devices": noop("Registered devices reset"),
    "disable_for_days": noop("Disabled for {days} days"),
    "disable_with_verification": noop(
        'Two factor disabled. Verified by: {verified_by}, verification mode: "{verification_mode}"'
    ),
    "reset_password": noop("Password reset"),
    "activate_user": noop('User re-enabled. Reason: "{reason}"'),
    "deactivate_user": noop('User disabled. Reason: "{reason}"'),
    "add_phone_numbers": noop('Added phone number(s) {phone_numbers}'),
    "remove_phone_numbers": noop('Removed phone number(s) {phone_numbers}'),
    "set_profile": noop("Profile: {name}[{id}]"),
    "clear_profile": noop("Profile: None"),
    "set_primary_location": noop("Primary location: {name}[{id}]"),
    "clear_primary_location": noop("Primary location: None"),
    "set_assigned_locations": noop("Assigned locations: {locations_info}"),
    "clear_assigned_locations": noop("Assigned locations: []"),
    "set_groups": noop("Groups: {groups_info}"),
    "clear_groups": noop("Groups: []"),
    "add_domain_invitation": noop("Invited to domain '{domain}'"),
    "remove_domain_invitation": noop("Invitation revoked for domain '{domain}'")
}


class UserChangeMessageV1(object):
    """
    Each change message to follow the structure
    {
        "field": {
            "slug": message_slug,
            "params": {} # optional params for the message
        }
    }
    field: could be domain, phone_numbers etc
    it is needed as the top-level key to make it searchable
    slug: any slug in MESSAGES
    params: (optional) params for the message
    """
    @staticmethod
    def program_change(program):
        if program:
            change_message = {"program": [
                {
                    "slug": "set_program",
                    "params": {"id": program.get_id, "name": program.name}
                }
            ]}
        else:
            change_message = {"program": [
                {"slug": "clear_program"}
            ]}
        return change_message

    @staticmethod
    def role_change(user_role):
        if user_role:
            change_message = {"role": [
                {
                    "slug": "set_role",
                    "params": {"id": user_role.get_qualified_id(), "name": user_role.name}
                }
            ]}
        else:
            change_message = {"role": [
                {"slug": "clear_role"}
            ]}
        return change_message

    @staticmethod
    def domain_removal(domain):
        return {"domain": [
            {
                "slug": "remove_from_domain",
                "params": {"name": domain}
            }
        ]}

    @staticmethod
    def registered_devices_reset():
        return {"devices": [
            {
                "slug": "reset_devices"
            }
        ]}

    @staticmethod
    def two_factor_disabled_for_days(days):
        return {"two_factor": [
            {
                "slug": "disable_for_days",
                "params": {"days": days}
            }
        ]}

    @staticmethod
    def two_factor_disabled_with_verification(verified_by, verification_mode):
        return {"two_factor": [
            {
                "slug": "disable_with_verification",
                "params": {
                    "verified_by": verified_by,
                    "verification_mode": verification_mode
                }
            }
        ]}

    @staticmethod
    def password_reset():
        return {"password": [
            {
                "slug": "reset_password"
            }
        ]}

    @staticmethod
    def status_update(active, reason):
        return {"status": [
            {
                "slug": "activate_user" if active else "deactivate_user",
                "params": {
                    "reason": reason
                }
            }
        ]}

    @staticmethod
    def phone_numbers_added(phone_numbers):
        return {"phone_numbers": [
            {
                "slug": "add_phone_numbers",
                "params": {
                    "phone_numbers": ",".join(phone_numbers)
                }
            }
        ]}

    @staticmethod
    def phone_numbers_removed(phone_numbers):
        return {"phone_numbers": [
            {
                "slug": "remove_phone_numbers",
                "params": {
                    "phone_numbers": ",".join(phone_numbers)
                }
            }
        ]}

    @staticmethod
    def profile_info(profile_id, profile_name=None):
        if profile_id:
            change_message = {"profile": [
                {
                    "slug": "set_profile",
                    "params": {"id": profile_id, "name": profile_name}
                }
            ]}
        else:
            change_message = {"profile": [
                {"slug": "clear_profile"}
            ]}
        return change_message

    @staticmethod
    def primary_location_removed():
        return {"location": [
            {"slug": "clear_primary_location"}
        ]}

    @staticmethod
    def primary_location_info(location):
        if location:
            change_message = {"location": [
                {
                    "slug": "set_primary_location",
                    "params": {"id": location.location_id, "name": location.name}
                }
            ]}
        else:
            change_message = {"location": [
                {"slug": "clear_primary_location"}
            ]}
        return change_message

    @staticmethod
    def assigned_locations_info(locations):
        if locations:
            change_message = {"assigned_locations": [
                {
                    "slug": "set_assigned_locations",
                    "params": {"locations": [
                        {'id': location.location_id, 'name': location.name}
                        for location in locations
                    ]}
                }
            ]}
        else:
            change_message = {"assigned_locations": [
                {"slug": "clear_assigned_locations"}
            ]}
        return change_message

    @staticmethod
    def groups_info(groups):
        if groups:
            change_message = {"groups": [
                {
                    "slug": "set_groups",
                    "params": {"groups": [
                        {'id': group.get_id, 'name': group.name}
                        for group in groups
                    ]}
                }
            ]}
        else:
            change_message = {"groups": [
                {"slug": "clear_groups"}
            ]}
        return change_message

    @staticmethod
    def added_as_web_user(domain):
        return {"domain": [
            {
                "slug": "add_as_web_user",
                "params": {"name": domain}
            }
        ]}

    @staticmethod
    def invited_to_domain(domain):
        return {"domain_invitation": [
            {
                "slug": "add_domain_invitation",
                "params": {"domain": domain}
            }
        ]}

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return {"domain_invitation": [
            {
                "slug": "remove_domain_invitation",
                "params": {"domain": domain}
            }
        ]}


class UserChangeMessageFormatterV1(object):
    """
    This class exposes just get_messages method which builds human readable
    messages for structured messages created by UserChangeMessageV1.
    """
    def get_messages(self, change_messages):
        formatted_messages = []
        for key, change_message in change_messages.items():
            if hasattr(self, f"_{key}_messages"):
                messages = getattr(self, f"_{key}_messages")(change_message)
            else:
                messages = []
                for change in change_message:
                    messages.append(_(MESSAGES[change['slug']]).format(**change.get('params', {})))
            formatted_messages.extend(messages)
        return formatted_messages

    @staticmethod
    def _assigned_locations_messages(change_message):
        messages = []
        for change in change_message:
            if change['slug'] == 'set_assigned_locations':
                locations_info = [f"{loc['name']}[{loc['id']}]" for loc in change['params']['locations']]
                messages.append(_(MESSAGES[change['slug']]).format(locations_info=locations_info))
            else:
                messages.append(_(MESSAGES[change['slug']]).format(**change.get('params', {})))
        return messages

    @staticmethod
    def _groups_messages(change_message):
        messages = []
        for change in change_message:
            if change['slug'] == 'set_groups':
                groups_info = [f"{group['name']}[{group['id']}]" for group in change['params']['groups']]
                messages.append(_(MESSAGES[change['slug']]).format(groups_info=groups_info))
            else:
                messages.append(_(MESSAGES[change['slug']]).format(**change.get('params', {})))
        return messages
