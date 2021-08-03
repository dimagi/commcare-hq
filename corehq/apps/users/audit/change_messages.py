class UserChangeMessage(object):
    @staticmethod
    def program_change(program):
        if program:
            change_message = {"program": {"id": program.get_id, "name": program.name}}
        else:
            change_message = {"program": {"id": None}}
        return change_message

    @staticmethod
    def role_change(user_role):
        if user_role:
            change_message = {'role': {'id': user_role.get_qualified_id(), 'name': user_role.name}}
        else:
            change_message = {'role': {'id': None}}
        return change_message

    @staticmethod
    def domain_removal(domain):
        return {"domain": {"removed": domain}}

    @staticmethod
    def registered_devices_reset():
        return {"devices": "reset"}

    @staticmethod
    def two_factor_disabled_for_days(days):
        return {"two_factor": {"disabled": True, "days": days}}

    @staticmethod
    def two_factor_disabled_with_verification(verified_by, verification_mode):
        return {
            "two_factor": {
                "disabled": True,
                "verified_by": verified_by,
                "verification_mode": verification_mode
            }
        }

    @staticmethod
    def password_reset():
        return {"password": "reset"}

    @staticmethod
    def status_update(active, reason):
        return {
            "active": active,
            "reason": reason
        }

    @staticmethod
    def phone_number_added(phone_number):
        # ToDo: dedup with phone_numbers_added
        return {
            "phone_number": {"added": [phone_number]}
        }

    @staticmethod
    def phone_numbers_added(phone_numbers):
        return {
            "phone_number": {"added": phone_numbers}
        }

    @staticmethod
    def phone_number_removed(phone_number):
        # ToDo: dedup with phone_numbers_removed
        return {
            "phone_number": {"removed": [phone_number]}
        }

    @staticmethod
    def phone_numbers_removed(phone_numbers):
        return {
            "phone_number": {"removed": phone_numbers}
        }

    @staticmethod
    def profile_info(profile_id, profile_name=None):
        if profile_id:
            change_message = {"profile": {"id": profile_id, "name": profile_name}}
        else:
            change_message = {"profile": {"id": None}}
        return change_message

    @staticmethod
    def primary_location_removed():
        return {"location": {"id": None}}

    @staticmethod
    def commcare_user_primary_location_info(location):
        # ToDo: Dedup with web_user_primary_location_info
        if location:
            change_message = {"location": {"id": location.location_id, "name": location.name}}
        else:
            change_message = {"location": {"id": None}}
        return change_message

    @staticmethod
    def web_user_primary_location_info(location):
        if location:
            change_message = {"location": {"id": location.location_id, "name": location.name}}
        else:
            change_message = {"location": {"id": None}}
        return change_message

    @staticmethod
    def commcare_user_assigned_locations_info(locations):
        # ToDo: Dedup with web_user_assigned_locations_info
        if locations:
            change_message = {
                "assigned_locations": [
                    {'id': location.location_id, 'name': location.name}
                    for location in locations
                ]
            }
        else:
            change_message = {"assigned_locations": []}
        return change_message

    @staticmethod
    def web_user_assigned_locations_info(locations):
        if locations:
            change_message = {
                "assigned_locations": [
                    {'id': location.location_id, 'name': location.name}
                    for location in locations
                ]
            }
        else:
            change_message = {"assigned_locations": []}
        return change_message

    @staticmethod
    def groups_info(groups):
        if groups:
            change_message = {'groups': [
                {'id': group.get_id, 'name': group.name}
                for group in groups
            ]}
        else:
            change_message = {'groups': []}
        return change_message

    @staticmethod
    def added_as_web_user(domain):
        return {"domain": {"added": domain}}

    @staticmethod
    def invited_to_domain(domain):
        return {"domain_invitation": {"added": [domain]}}

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return {"domain_invitation": {"revoked": [domain]}}
