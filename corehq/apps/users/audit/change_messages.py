from enum import Enum
from django.utils.translation import ugettext as _


class Change(Enum):
    SET = 'set'
    RESET = 'reset'
    REMOVE = 'remove'
    ADD = 'add'


class UserChangeMessageV1(object):
    """
    Each change message to follow the structure
    {
        "field": {
            "change": change_details
        }
    }
    field: could be domain, phone_numbers etc
    change: either 'set' / 'reset' / 'remove' / 'add'
    change_details: a Boolean or
                    a dict with details as needed for the change
                    a list of a dicts as needed for the change
    """
    @staticmethod
    def program_change(program):
        if program:
            change_message = {"program": {Change.SET: {"id": program.get_id, "name": program.name}}}
        else:
            change_message = {"program": {Change.SET: {}}}
        return change_message

    @staticmethod
    def role_change(user_role):
        if user_role:
            change_message = {"role": {Change.SET: {"id": user_role.get_qualified_id(), "name": user_role.name}}}
        else:
            change_message = {"role": {Change.SET: {}}}
        return change_message

    @staticmethod
    def domain_removal(domain):
        return {"domain": {Change.REMOVE: {"name": domain}}}

    @staticmethod
    def registered_devices_reset():
        return {"devices": {Change.RESET: True}}

    @staticmethod
    def two_factor_disabled_for_days(days):
        return {"two_factor": {Change.REMOVE: {"days": days}}}

    @staticmethod
    def two_factor_disabled_with_verification(verified_by, verification_mode):
        return {
            "two_factor": {
                Change.REMOVE: {
                    "verified_by": verified_by,
                    "verification_mode": verification_mode
                }
            }
        }

    @staticmethod
    def password_reset():
        return {"password": {Change.RESET: True}}

    @staticmethod
    def status_update(active, reason):
        return {
            "status": {
                Change.SET: {
                    "active": active,
                    "reason": reason
                }
            }
        }

    @staticmethod
    def phone_numbers_added(phone_numbers):
        return {
            "phone_numbers": {Change.ADD: phone_numbers}
        }

    @staticmethod
    def phone_numbers_removed(phone_numbers):
        return {
            "phone_numbers": {Change.REMOVE: phone_numbers}
        }

    @staticmethod
    def profile_info(profile_id, profile_name=None):
        if profile_id:
            change_message = {"profile": {Change.SET: {"id": profile_id, "name": profile_name}}}
        else:
            change_message = {"profile": {Change.SET: {}}}
        return change_message

    @staticmethod
    def primary_location_removed():
        return {"location": {Change.SET: {}}}

    @staticmethod
    def primary_location_info(location):
        if location:
            change_message = {"location": {Change.SET: {"id": location.location_id, "name": location.name}}}
        else:
            change_message = {"location": {Change.SET: {}}}
        return change_message

    @staticmethod
    def assigned_locations_info(locations):
        if locations:
            change_message = {
                "assigned_locations": {Change.SET: [
                    {'id': location.location_id, 'name': location.name}
                    for location in locations
                ]}
            }
        else:
            change_message = {"assigned_locations": {Change.SET: []}}
        return change_message

    @staticmethod
    def groups_info(groups):
        if groups:
            change_message = {"groups": {Change.SET: [
                {'id': group.get_id, 'name': group.name}
                for group in groups
            ]}}
        else:
            change_message = {"groups": {Change.SET: []}}
        return change_message

    @staticmethod
    def added_as_web_user(domain):
        return {"domain": {Change.ADD: {"name": domain, "web_user": True}}}

    @staticmethod
    def invited_to_domain(domain):
        return {"domain_invitation": {Change.ADD: {'domain': domain}}}

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return {"domain_invitation": {Change.REMOVE: {'domain': domain}}}


class UserChangeMessageFormatterV1(object):
    """
    This class exposes just get_messages method which builds human readable
    messages for structured messages created by UserChangeMessageV1.

    It simply has a method _{change_slug}_messages for each change slug added by
    UserChangeMessageV1
    """
    def get_messages(self, change_messages):
        formatted_messages = []
        for key, change_message in change_messages.items():
            if hasattr(self, f"_{key}_messages"):
                messages = getattr(self, f"_{key}_messages")(change_message)
                if messages:

                    formatted_messages.extend(messages)
        return formatted_messages

    @staticmethod
    def _program_messages(change_message):
        messages = []
        if Change.SET in change_message:
            new_program = change_message[Change.SET]
            if new_program:
                messages.append(_("Program: {program_name}[{program_id}]").format(
                    program_name=new_program['name'],
                    program_id=new_program['id']
                ))
            else:
                messages.append(_("Program: None"))
        return messages

    @staticmethod
    def _role_messages(change_message):
        messages = []
        if Change.SET in change_message:
            new_role = change_message[Change.SET]
            if new_role:
                messages.append(_("Role: {role_name}[{role_id}]").format(
                    role_name=new_role['name'],
                    role_id=new_role['id']
                ))
            else:
                messages.append(_("Role: None"))
        return messages

    @staticmethod
    def _domain_messages(change_message):
        messages = []
        if Change.REMOVE in change_message:
            messages.append(_("Removed from domain '{domain}'").format(
                domain=change_message[Change.REMOVE]["name"]
            ))
        elif Change.ADD in change_message:
            change = change_message[Change.ADD]
            if change.get('web_user'):
                messages.append(_("Added as web user to domain '{domain}'").format(
                    domain=change_message['name']
                ))
        return messages

    @staticmethod
    def _devices_messages(change_message):
        messages = []
        if change_message.get(Change.RESET):
            messages.append(_("Registered devices reset"))
        return messages

    @staticmethod
    def _two_factor_messages(change_message):
        messages = []
        if Change.REMOVE in change_message:
            change = change_message[Change.REMOVE]
            if change.get('days'):
                messages.append(_("Disabled for {days} days").format(
                    days=change['days']
                ))
            elif change.get('verified_by'):
                messages.append(
                    _('Two factor disabled. '
                      'Verified by: {verified_by}, verification mode: "{verification_mode}"'
                      ).format(verified_by=change['verified_by'],
                               verification_mode=change['verification_mode'])
                )
        return messages

    @staticmethod
    def _password_messages(change_message):
        messages = []
        if change_message.get(Change.RESET):
            messages.append(_("Password reset"))
        return messages

    @staticmethod
    def _status_messages(change_message):
        messages = []
        if Change.SET in change_message:
            change = change_message[Change.SET]
            if change['active']:
                messages.append(
                    _('User re-enabled. Reason: "{reason}"').format(
                        reason=change['reason']
                    )
                )
            else:
                messages.append(
                    _('User disabled. Reason: "{reason}"').format(
                        reason=change['reason']
                    )
                )
        return messages

    @staticmethod
    def _phone_numbers_messages(change_message):
        messages = []
        if Change.ADD in change_message:
            messages.append(_(
                "Added phone number(s) {phone_numbers}"
            ).format(phone_numbers=", ".join(change_message[Change.ADD])))
        if Change.REMOVE in change_message:
            messages.append(_(
                "Removed phone number(s) {phone_numbers}"
            ).format(phone_numbers=", ".join(change_message[Change.REMOVE])))
        return messages

    @staticmethod
    def _profile_messages(change_message):
        messages = []
        if Change.SET in change_message:
            new_profile = change_message[Change.SET]
            if new_profile:
                messages.append(_("Profile: {profile_name}[{profile_id}]").format(
                    profile_name=new_profile['name'],
                    profile_id=new_profile['id']
                ))
            else:
                messages.append(_("Profile: None"))
        return messages

    @staticmethod
    def _location_messages(change_message):
        messages = []
        if Change.SET in change_message:
            new_location = change_message[Change.SET]
            if new_location:
                messages.append(_("Primary location: {location_name}[{location_id}]").format(
                    location_name=new_location['name'],
                    location_id=new_location['id']
                ))
            else:
                messages.append(_("Primary location: None"))
        return messages

    @staticmethod
    def _assigned_locations_messages(change_message):
        messages = []
        if Change.SET in change_message:
            locations_info = [f"{info['name']}[{info['id']}]" for info in change_message[Change.SET]]
            messages.append(_("Assigned locations: {locations_info}").format(locations_info=locations_info))
        return messages

    @staticmethod
    def _groups_messages(change_message):
        messages = []
        if Change.SET in change_message:
            groups_info = [f"{info['name']}[{info['id']}]" for info in change_message[Change.SET]]
            messages.append(_("Groups: {groups_info}").format(groups_info=groups_info))
        return messages

    @staticmethod
    def _domain_invitation_messages(change_message):
        messages = []
        if change_message.get(Change.ADD):
            messages.append(_("Invited to domain '{domain}'").format(
                domain=change_message[Change.ADD]["domain"]
            ))
        if change_message.get(Change.REMOVE):
            messages.append(_("Invitation revoked for domain '{domain}'").format(
                domain=change_message[Change.REMOVE]["domain"]
            ))
        return messages
