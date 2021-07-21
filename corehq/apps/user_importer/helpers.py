from dimagi.utils.parsing import string_to_boolean

from corehq.apps.custom_data_fields.models import PROFILE_SLUG
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
    """
    User change logger to record
        - changes to user properties
        - text messages for changes
        - useful info for changes to associated data models like role/locations
    """
    def __init__(self, domain, user, is_new_user, changed_by_user, changed_via, upload_record_id):
        self.domain = domain
        self.user = user
        self.is_new_user = is_new_user
        self.changed_by_user = changed_by_user
        self.changed_via = changed_via
        self.upload_record_id = upload_record_id

        if not is_new_user:
            self.original_user_doc = self.user.to_json()
        else:
            self.original_user_doc = None

        self.fields_changed = {}
        self.messages = []

        self._save = False  # flag to check if log needs to be saved for updates

    def add_changes(self, changes):
        """
        Add changes to user properties.
        Ignored for new user since the whole user doc is logged for a new user
        :param changes: dict of property mapped to it's new value
        """
        if self.is_new_user:
            return
        for name, new_value in changes.items():
            if self.original_user_doc[name] != new_value:
                self.fields_changed[name] = new_value
                self._save = True

    def add_change_message(self, message):
        """
        Add raw/untranslated text messages for changes that are not exactly user properties.
        Ignored for new user since the whole user doc is logged for a new user
        :param message: text message for the change like 'Password Reset' / 'Added as web user to domain foo'
        """
        if self.is_new_user:
            return
        self.messages.append(message)
        self._save = True

    def add_info(self, info):
        """
        Useful raw/untranslated info for display, specifically of associated data models like roles/locations.
        Info will also include ID if the data model is not linked directly on the user like
        primary location for CommCareUser is present on the user record but for a WebUser it's
        stored on Domain Membership. So for WebUser, info should also include the primary location's location id.
        :param info: text info like "Role: RoleName[role_id]" / "Primary Location: Boston[boston-location-id]"
        """
        self.messages.append(info)
        self._save = True

    def save(self):
        if self.is_new_user or self._save:
            action = UserModelAction.CREATE if self.is_new_user else UserModelAction.UPDATE
            fields_changed = None if self.is_new_user else self.fields_changed
            log_user_change(
                self.domain,
                self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                message=". ".join(self.messages),
                action=action,
                fields_changed=fields_changed,
                bulk_upload_record_id=self.upload_record_id,
            )


class BaseUserImporter(object):
    """
    Imports a Web/CommCareUser via bulk importer and also handles the logging
    save_log should be called explicitly to save logs, after user is saved
    """
    def __init__(self, upload_domain, user_domain, user, upload_user, is_new_user, via, upload_record_id):
        """
        :param upload_domain: domain on which the bulk upload is being done
        :param user_domain: domain user is being updated for
        :param user: user to update
        :param upload_user: user doing the upload
        :param is_new_user: if user is a new user
        :param via: USER_CHANGE_VIA_BULK_IMPORTER
        :param upload_record_id: ID of the bulk upload record
        """
        self.user_domain = user_domain
        self.user = user
        self.upload_user = upload_user
        self.logger = UserChangeLogger(upload_domain, user=user, is_new_user=is_new_user,
                                       changed_by_user=upload_user, changed_via=via,
                                       upload_record_id=upload_record_id)

        self.role_updated = False

    def update_role(self, role_qualified_id):
        user_current_role = self.user.get_role(domain=self.user_domain)
        self.role_updated = not (user_current_role
                                 and user_current_role.get_qualified_id() == role_qualified_id)
        if self.role_updated:
            self.user.set_role(self.user_domain, role_qualified_id)

    def save_log(self):
        # Tracking for role is done post save to have role setup correctly on save
        if self.role_updated:
            new_role = self.user.get_role(domain=self.user_domain)
            if new_role:
                self.logger.add_info(f"Role: {new_role.name}[{new_role.get_qualified_id()}]")
            else:
                self.logger.add_info("Role: None")

        self._include_user_data_changes()
        self.logger.save()

    def _include_user_data_changes(self):
        # ToDo: consider putting just the diff
        if self.logger.original_user_doc and self.logger.original_user_doc['user_data'] != self.user.user_data:
            self.logger.add_changes({'user_data': self.user.user_data})


class CommCareUserImporter(BaseUserImporter):
    def update_password(self, password):
        self.user.set_password(password)
        self.logger.add_change_message("Password Reset")

    def update_phone_number(self, phone_number):
        fmt_phone_number = _fmt_phone(phone_number)
        if fmt_phone_number not in self.user.phone_numbers:
            self.logger.add_change_message(f"Added phone number {fmt_phone_number}")
        # always call this to set phone number as default if needed
        self.user.add_phone_number(fmt_phone_number, default=True)

    def update_name(self, name):
        self.user.set_full_name(str(name))
        self.logger.add_changes({'first_name': self.user.first_name, 'last_name': self.user.last_name})

    def update_user_data(self, data, uncategorized_data, profile, domain_info):
        # Add in existing data. Don't use metadata - we don't want to add profile-controlled fields.
        current_profile_id = self.user.user_data.get(PROFILE_SLUG)

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

        if self.user.user_data.get(PROFILE_SLUG) and self.user.user_data[PROFILE_SLUG] != current_profile_id:
            self.logger.add_info("CommCare Profile: {profile_name}".format(
                profile_name=domain_info.profile_name_by_id[self.user.user_data[PROFILE_SLUG]])
            )

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
        from corehq.apps.user_importer.importer import (
            check_modified_user_loc,
            find_location_id,
            get_location_from_site_code
        )

        location_ids = find_location_id(location_codes, domain_info.location_cache)
        user_current_primary_location_id = self.user.location_id
        locations_updated, primary_loc_removed = check_modified_user_loc(location_ids,
                                                                         self.user.location_id,
                                                                         self.user.assigned_location_ids)
        if primary_loc_removed:
            self.user.unset_location(commit=False)
        if locations_updated:
            self.user.reset_locations(location_ids, commit=False)
            self.logger.add_changes({'assigned_location_ids': location_ids})
            if location_ids:
                location_names = [get_location_from_site_code(code, domain_info.location_cache).name
                                  for code in location_codes]
                self.logger.add_info(f"Assigned locations: {location_names}")

        # log this after assigned locations are updated, which can re-set primary location
        if self.user.location_id != user_current_primary_location_id:
            self.logger.add_changes({'location_id': self.user.location_id})
            if self.user.location_id:
                user_updated_primary_location_name = get_user_primary_location_name(self.user, self.user_domain)
                self.logger.add_info(f"Primary location: {user_updated_primary_location_name}")


def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, str):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")


class WebUserImporter(BaseUserImporter):
    def add_to_domain(self, role_qualified_id, location_id):
        self.user.add_as_web_user(self.user_domain, role=role_qualified_id, location_id=location_id)
        self.role_updated = bool(role_qualified_id)

        self.logger.add_change_message(f"Added as web user to domain '{self.user_domain}'")
        if location_id:
            self._log_primary_location_info()

    def _log_primary_location_info(self):
        primary_location = self.user.get_sql_location(self.user_domain)
        self.logger.add_info(f"Primary location: {primary_location.name}[{primary_location.location_id}]")

    def update_primary_location(self, location_id):
        current_primary_location_id = get_user_primary_location_id(self.user, self.user_domain)
        if location_id:
            self.user.set_location(self.user_domain, location_id)
            if current_primary_location_id != location_id:
                self._log_primary_location_info()
        else:
            self.user.unset_location(self.user_domain)
            # if there was a location before, log that it was cleared
            if current_primary_location_id:
                self.logger.add_info("Primary location: None")

    def update_locations(self, location_codes, membership, domain_info):
        from corehq.apps.user_importer.importer import (
            check_modified_user_loc,
            find_location_id,
            get_location_from_site_code
        )

        location_ids = find_location_id(location_codes, domain_info.location_cache)
        user_current_primary_location_id = membership.location_id
        locations_updated, primary_loc_removed = check_modified_user_loc(location_ids,
                                                                         membership.location_id,
                                                                         membership.assigned_location_ids)
        if primary_loc_removed:
            self.user.unset_location(self.user_domain, commit=False)
        if locations_updated:
            self.user.reset_locations(self.user_domain, location_ids, commit=False)
            if location_ids:
                locations = [get_location_from_site_code(code, domain_info.location_cache)
                             for code in location_codes]
                locations_info = ", ".join([f"{location.name}[{location.location_id}]" for location in locations])
            else:
                locations_info = []
            self.logger.add_info(f"Assigned locations: {locations_info}")

        # log this after assigned locations are updated, which can re-set primary location
        user_updated_primary_location_id = get_user_primary_location_id(self.user, self.user_domain)
        if user_updated_primary_location_id != user_current_primary_location_id:
            if user_updated_primary_location_id:
                self._log_primary_location_info()
            else:
                self.logger.add_info("Primary location: None")


def get_user_primary_location_id(user, domain):
    primary_location = user.get_sql_location(domain)
    if primary_location:
        return primary_location.location_id


def get_user_primary_location_name(user, domain):
    primary_location = user.get_sql_location(domain)
    if primary_location:
        return primary_location.name
