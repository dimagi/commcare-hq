class UserChangeMessage(object):
    @staticmethod
    def program_change(program):
        if program:
            message = f"Program: {program.name}[{program.get_id}]"
        else:
            message = 'Program: None'
        return message

    @staticmethod
    def role_change(user_role):
        message = 'Role: None'
        if user_role:
            message = f"Role: {user_role.name}[{user_role.get_qualified_id()}]"
        return message

    @staticmethod
    def domain_removal(domain):
        return f"Removed from domain '{domain}'"

    @staticmethod
    def registered_devices_reset():
        return "Registered devices reset"

    @staticmethod
    def two_factor_disabled_for_days(days):
        return f"Disabled for {days} days"

    @staticmethod
    def two_factor_disabled_with_verification(verified_by, verification_mode):
        return f'Two factor disabled. Verified by: {verified_by}, verification mode: "{verification_mode}"'

    @staticmethod
    def password_reset():
        return "Password reset"

    @staticmethod
    def status_update(action, reason):
        return f'User {action}. Reason: "{reason}"'

    @staticmethod
    def phone_number_added(phone_number):
        return f"Added phone number {phone_number}"

    @staticmethod
    def phone_number_removed(phone_number):
        return f"Removed phone number {phone_number}"

    @staticmethod
    def profile_info(profile_name):
        return f"CommCare Profile: {profile_name}"

    @staticmethod
    def primary_location_removed():
        return "Primary location: None"

    @staticmethod
    def commcare_user_primary_location_info(location_name):
        return f"Primary location: {location_name}"

    @staticmethod
    def web_user_primary_location_info(location):
        if location:
            message = f"Primary location: {location.name}[{location.location_id}]"
        else:
            message = "Primary location: None"
        return message

    @staticmethod
    def commcare_user_assigned_locations_info(location_names):
        return f"Assigned locations: {location_names}"

    @staticmethod
    def web_user_assigned_locations_info(locations_info):
        return f"Assigned locations: {locations_info}"

    @staticmethod
    def groups_info(groups_info):
        return f"Groups: {groups_info}"

    @staticmethod
    def added_as_web_user(domain):
        return f"Added as web user to domain '{domain}'"

    @staticmethod
    def invited_to_domain(domain):
        return f"Invited to domain '{domain}'"

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return f"Invitation revoked for domain '{domain}'"
