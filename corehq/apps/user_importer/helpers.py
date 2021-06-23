from dimagi.utils.parsing import string_to_boolean
from django.utils.translation import ugettext as _

from corehq.apps.custom_data_fields.models import PROFILE_SLUG
from corehq.apps.locations.models import SQLLocation
from corehq.apps.user_importer.exceptions import UserUploadError

from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.util import log_user_change


def spec_value_to_boolean_or_none(user_spec_dict, key):
    value = user_spec_dict.get(key, None)
    if value and isinstance(value, str):
        return string_to_boolean(value)
    elif isinstance(value, bool):
        return value
    else:
        return None


class UserChangeLogger(object):
    def __init__(self, domain, user, is_new_user, changed_by_user, changed_via):
        self.domain = domain
        self.user = user
        self.is_new_user = is_new_user
        self.changed_by_user = changed_by_user
        self.changed_via = changed_via

        self.original_user_doc = self.user.to_json()
        self.fields_changed = {}
        self.messages = []

        self._save = False  # flag to check if log needs to be saved for updates

    def add_changes(self, changes):
        # ignore for new user since the whole user doc is logged for a new user
        if self.is_new_user:
            return
        for name, new_value in changes.items():
            if self.original_user_doc[name] != new_value:
                self.fields_changed[name] = new_value
                self._save = True

    def add_change_message(self, message):
        # ignore for new user since the whole user doc is logged for a new user
        if self.is_new_user:
            return
        self.messages.append(message)
        self._save = True

    def add_info(self, info):
        # useful info for display like names
        self.messages.append(info)
        self._save = True

    def save(self):
        self._include_user_data_changes()
        if self.is_new_user:
            log_user_change(
                self.domain,
                self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                message=". ".join(self.messages),
                action=UserModelAction.CREATE,
            )
        else:
            if not self._save:
                return
            log_user_change(
                self.domain,
                self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                message=". ".join(self.messages),
                fields_changed=self.fields_changed
            )

    def _include_user_data_changes(self):
        # ToDo: consider putting just the diff
        if self.original_user_doc['user_data'] != self.user.user_data:
            self.fields_changed['user_data'] = self.user.user_data
            self._save = True


class CommCareUserImporter(object):
    def __init__(self, upload_domain, user_domain, user, upload_user, is_new_user, via):
        self.user_domain = user_domain
        self.user = user
        self.logger = UserChangeLogger(upload_domain, user=user, is_new_user=is_new_user,
                                       changed_by_user=upload_user, changed_via=via)
        self.role_updated = False

    def update_password(self, password):
        self.user.set_password(password)
        self.logger.add_change_message(_("Password Reset"))

    def update_phone_number(self, phone_number):
        fmt_phone_number = _fmt_phone(phone_number)
        # always call this to set phone number as default if needed
        self.user.add_phone_number(fmt_phone_number, default=True)
        if fmt_phone_number not in self.user.phone_numbers:
            self.logger.add_change_message(_(f"Added phone number {fmt_phone_number}"))

    def update_name(self, name):
        self.user.set_full_name(str(name))
        self.logger.add_changes({'first_name': self.user.first_name, 'last_name': self.user.last_name})

    def update_user_data(self, data, uncategorized_data, profile, domain_info):
        # Add in existing data. Don't use metadata - we don't want to add profile-controlled fields.
        for key, value in self.user.user_data.items():
            if key not in data:
                data[key] = value
        if profile:
            profile_obj = domain_info.profiles_by_name[profile]
            data[PROFILE_SLUG] = profile_obj.id
            for key in profile_obj.fields.keys():
                self.user.pop_metadata(key)
        try:
            self.user.update_metadata(data)
        except ValueError as e:
            raise UserUploadError(str(e))
        if uncategorized_data:
            self.user.update_metadata(uncategorized_data)

        # Clear blank user data so that it can be purged by remove_unused_custom_fields_from_users_task
        for key in dict(data, **uncategorized_data):
            value = self.user.metadata[key]
            if value is None or value == '':
                self.user.pop_metadata(key)

    def update_language(self, language):
        self.user.language = language
        self.logger.add_changes({'language': language})

    def update_email(self, email):
        self.user.email = email.lower()
        self.logger.add_changes({'email': self.user.email})

    def update_status(self, is_active):
        self.user.is_active = is_active
        self.logger.add_changes({'is_active': is_active})

    def update_locations(self, location_codes, domain_info):
        from corehq.apps.user_importer.importer import find_location_id, check_modified_user_loc

        location_ids = find_location_id(location_codes, domain_info.location_cache)
        users_current_primary_location_id = self.user.location_id
        locations_updated, primary_loc_removed = check_modified_user_loc(location_ids,
                                                                         self.user.location_id,
                                                                         self.user.assigned_location_ids)
        if primary_loc_removed:
            self.user.unset_location(commit=False)
        if locations_updated:
            self.user.reset_locations(location_ids, commit=False)
            self.logger.add_changes({'assigned_location_ids': location_ids})
            if location_ids:
                location_names = list(SQLLocation.active_objects.filter(
                    location_id__in=location_ids
                ).values_list('name', flat=True))
                self.logger.add_info(_(f"Assigned locations: {location_names}"))
        # log this after assigned locations are updated, which can re-set primary location
        if self.user.location_id != users_current_primary_location_id:
            self.logger.add_changes({'location_id': self.user.location_id})
            if self.user.location_id:
                self.logger.add_info(
                    _(f"Primary location: {self.user.get_sql_location(self.user_domain).name}"))

    def update_role(self, role, domain_info):
        role_qualified_id = domain_info.roles_by_name[role]
        user_current_role = self.user.get_role(domain=self.user_domain)
        self.role_updated = not (user_current_role
                                 and user_current_role.get_qualified_id() == role_qualified_id)
        if self.role_updated:
            self.user.set_role(self.user_domain, role_qualified_id)

    def save(self):
        self.user.save()

        # Tracking for role is done post save to have role setup correctly on save
        if self.role_updated:
            new_role = self.user.get_role(domain=self.user_domain)
            if new_role:
                self.logger.add_info(_(f"Role: {new_role.name}[{new_role.get_id}]"))
            else:
                self.logger.add_change_message("Role: None")

        # ToDo: save log before saving user
        self.logger.save()


def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, str):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")
