class UserChangeMessage(object):
    @staticmethod
    def role_change_message(user_role):
        message = 'Role: None'
        if user_role:
            message = f"Role: {user_role.name}[{user_role.get_qualified_id()}]"
        return message

    @staticmethod
    def domain_removal_message(domain):
        return f"Removed from domain '{domain}'"

    @staticmethod
    def registered_devices_reset_message():
        return "Registered devices reset"

    @staticmethod
    def two_factor_disabled_for_days_message(days):
        return f"Disabled for {days} days"

    @staticmethod
    def two_factor_disabled_with_verification_message(verified_by, verification_mode):
        return f'Two factor disabled. Verified by: {verified_by}, verification mode: "{verification_mode}"'

    @staticmethod
    def password_reset_message():
        return "Password reset"

    @staticmethod
    def status_update_message(action, reason):
        return f'User {action}. Reason: "{reason}"'

    @staticmethod
    def phone_number_added_message(phone_number):
        return f"Added phone number {phone_number}"

    @staticmethod
    def profile_info_message(profile_name):
        return f"CommCare Profile: {profile_name}"

    @staticmethod
    def primary_location_removed_message():
        return "Primary location: None"

    @staticmethod
    def commcare_user_primary_location_info_message(location_name):
        return f"Primary location: {location_name}"

    @staticmethod
    def web_user_primary_location_info_message(location):
        return f"Primary location: {location.name}[{location.location_id}]"

    @staticmethod
    def commcare_user_assigned_locations_info_message(location_names):
        return f"Assigned locations: {location_names}"

    @staticmethod
    def web_user_assigned_locations_info_message(locations_info):
        return f"Assigned locations: {locations_info}"

    @staticmethod
    def groups_info_message(groups_info):
        return f"Groups: {groups_info}"

    @staticmethod
    def added_as_web_user_message(domain):
        return f"Added as web user to domain '{domain}'"

    @staticmethod
    def invited_to_domain(domain):
        return f"Invited to domain '{domain}'"

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return f"Invitation revoked for domain '{domain}'"
