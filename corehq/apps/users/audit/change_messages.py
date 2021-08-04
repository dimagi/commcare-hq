from django.utils.translation import ugettext as _


class UserChangeMessageV1(object):
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
        return {"devices": {"reset": True}}

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
        return {"password": {"reset": True}}

    @staticmethod
    def status_update(active, reason):
        return {
            "status": {
                "active": active,
                "reason": reason
            }
        }

    @staticmethod
    def phone_numbers_added(phone_numbers):
        return {
            "phone_numbers": {"added": phone_numbers}
        }

    @staticmethod
    def phone_numbers_removed(phone_numbers):
        return {
            "phone_numbers": {"removed": phone_numbers}
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
    def primary_location_info(location):
        if location:
            change_message = {"location": {"id": location.location_id, "name": location.name}}
        else:
            change_message = {"location": {"id": None}}
        return change_message

    @staticmethod
    def assigned_locations_info(locations):
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
        return {"domain": {"added": domain, "web_user": True}}

    @staticmethod
    def invited_to_domain(domain):
        return {"domain_invitation": {"added": [domain]}}

    @staticmethod
    def invitation_revoked_for_domain(domain):
        return {"domain_invitation": {"revoked": [domain]}}


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
        if change_message["id"]:
            messages.append(_("Program: {program_name}[{program_id}]").format(
                program_name=change_message['name'],
                program_id=change_message['id']
            ))
        else:
            messages.append(_('Program: None'))
        return messages

    @staticmethod
    def _role_messages(change_message):
        messages = []
        if change_message["id"]:
            messages.append(_("Role: {role_name}[{role_id}]").format(
                role_name=change_message['name'],
                role_id=change_message['id']
            ))
        else:
            messages.append(_('Role: None'))
        return messages

    @staticmethod
    def _domain_messages(change_message):
        messages = []
        if change_message.get("removed"):
            messages.append(_("Removed from domain '{domain}'").format(
                domain=change_message.get("removed")
            ))
        elif change_message.get("added") and change_message.get("web_user"):
            messages.append(_("Added as web user to domain '{domain}'").format(
                domain=change_message.get("added")
            ))
        return messages

    @staticmethod
    def _devices_messages(change_message):
        messages = []
        if change_message.get("reset"):
            messages.append(_("Registered devices reset"))
        return messages

    @staticmethod
    def _two_factor_messages(change_message):
        messages = []
        if change_message.get('disabled'):
            if change_message.get('days'):
                messages.append(_("Disabled for {days} days").format(
                    days=change_message.get('days')
                ))
            elif change_message.get('verified_by'):
                messages.append(
                    _('Two factor disabled. '
                      'Verified by: {verified_by}, verification mode: "{verification_mode}"'
                      ).format(verified_by=change_message['verified_by'],
                               verification_mode=change_message['verification_mode'])
                )
        return messages

    @staticmethod
    def _password_messages(change_message):
        messages = []
        if change_message.get("reset"):
            messages.append(_("Password reset"))
        return messages

    @staticmethod
    def _status_messages(change_message):
        messages = []
        if change_message['active']:
            messages.append(
                _('User re-enabled. Reason: "{reason}"').format(
                    reason=change_message['reason']
                )
            )
        else:
            messages.append(
                _('User disabled. Reason: "{reason}"').format(
                    reason=change_message['reason']
                )
            )
        return messages

    @staticmethod
    def _phone_numbers_messages(change_message):
        messages = []
        if change_message.get("added"):
            messages.append(_(
                "Added phone number(s) {phone_numbers}"
            ).format(phone_numbers=", ".join(change_message.get("added"))))
        elif change_message.get("removed"):
            messages.append(_(
                "Removed phone number(s) {phone_numbers}"
            ).format(phone_numbers=", ".join(change_message.get("removed"))))
        return messages

    @staticmethod
    def _profile_messages(change_message):
        messages = []
        if change_message["id"]:
            messages.append(_("Profile: {profile_name}[{profile_id}]").format(
                profile_name=change_message['name'],
                profile_id=change_message['id']
            ))
        else:
            messages.append(_('Profile: None'))
        return messages

    @staticmethod
    def _location_messages(change_message):
        messages = []
        if change_message["id"]:
            messages.append(_("Primary location: {location_name}[{location_id}]").format(
                location_name=change_message['name'],
                location_id=change_message['id']
            ))
        else:
            messages.append(_('Primary location: None'))
        return messages

    @staticmethod
    def _assigned_locations_messages(change_message):
        messages = []
        locations_info = [f"{info['name']}[{info['id']}]" for info in change_message]
        messages.append(_("Assigned locations: {locations_info}").format(locations_info=locations_info))
        return messages

    @staticmethod
    def _groups_messages(change_message):
        messages = []
        groups_info = [f"{info['name']}[{info['id']}]" for info in change_message]
        messages.append(_("Groups: {groups_info}").format(groups_info=groups_info))
        return messages

    @staticmethod
    def _domain_invitation_messages(change_message):
        messages = []
        if change_message.get("added"):
            messages.append(_("Invited to domain '{domain}'").format(
                domain=change_message.get("added")
            ))
        elif change_message.get("revoked"):
            messages.append(_("Invitation revoked for domain '{domain}'").format(
                domain=change_message.get("revoked")
            ))
        return messages
