from django.utils.translation import gettext as _

from dimagi.utils.parsing import string_to_boolean

from corehq.apps.custom_data_fields.models import PROFILE_SLUG
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.model_log import UserModelAction
from corehq.apps.users.models import DeactivateMobileWorkerTrigger
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

    def __init__(self, upload_domain, user_domain, user, is_new_user, changed_by_user, changed_via,
                 upload_record_id, user_domain_required_for_log=True):
        self.upload_domain = upload_domain
        self.user_domain = user_domain
        self.user = user
        self.is_new_user = is_new_user
        self.changed_by_user = changed_by_user
        self.changed_via = changed_via
        self.upload_record_id = upload_record_id
        self.user_domain_required_for_log = user_domain_required_for_log

        if not is_new_user:
            self.original_user_doc = self.user.to_json()
            self.original_user_data = self.user.get_user_data(user_domain).raw
        else:
            self.original_user_doc = None
            self.original_user_data = None

        self.fields_changed = {}
        self.change_messages = {}

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
        Add change message for a change in user property that is in form of a UserChangeMessage
        Ignored for new user since the whole user doc is logged for a new user
        :param message: text message for the change like 'Password reset' / 'Added as web user to domain foo'
        """
        if self.is_new_user:
            return
        self._update_change_messages(message)
        self._save = True

    def _update_change_messages(self, change_messages):
        for slug in change_messages:
            if slug in self.change_messages:
                raise UserUploadError(_("Double Entry for {}").format(slug))
        self.change_messages.update(change_messages)

    def add_info(self, change_message):
        """
        Add change message for a change to the user that is in form of a UserChangeMessage
        """
        self._update_change_messages(change_message)
        self._save = True

    def save(self):
        if self.is_new_user or self._save:
            action = UserModelAction.CREATE if self.is_new_user else UserModelAction.UPDATE
            fields_changed = None if self.is_new_user else self.fields_changed
            return log_user_change(
                by_domain=self.upload_domain,
                for_domain=self.user_domain,
                couch_user=self.user,
                changed_by_user=self.changed_by_user,
                changed_via=self.changed_via,
                change_messages=self.change_messages,
                action=action,
                fields_changed=fields_changed,
                bulk_upload_record_id=self.upload_record_id,
                for_domain_required_for_log=self.user_domain_required_for_log,
            )

    def save_only_group_changes(self, group_change_message):
        return log_user_change(
            by_domain=self.upload_domain,
            for_domain=self.user_domain,
            couch_user=self.user,
            changed_by_user=self.changed_by_user,
            changed_via=self.changed_via,
            change_messages=group_change_message,
            action=UserModelAction.UPDATE,
            bulk_upload_record_id=self.upload_record_id,
            for_domain_required_for_log=self.user_domain_required_for_log,
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
        self.logger = UserChangeLogger(upload_domain=upload_domain, user_domain=user_domain, user=user,
                                       is_new_user=is_new_user,
                                       changed_by_user=upload_user, changed_via=via,
                                       upload_record_id=upload_record_id)

        self.role_updated = False

    def update_role(self, role_qualified_id):
        user_current_role = self.user.get_role(domain=self.user_domain)
        self.role_updated = not (user_current_role
                                 and user_current_role.get_qualified_id() == role_qualified_id)

        if self.role_updated:
            self.user.set_role(self.user_domain, role_qualified_id)

    def update_user_data(self, data, uncategorized_data, profile_name, profiles_by_name):
        from corehq.apps.users.user_data import UserDataError
        user_data = self.user.get_user_data(self.user_domain)
        old_profile_id = user_data.profile_id
        if PROFILE_SLUG in data:
            raise UserUploadError(_("You cannot set {} directly").format(PROFILE_SLUG))
        if profile_name:
            profile_id = profiles_by_name[profile_name].pk

        try:
            user_data.update(data, profile_id=profile_id if profile_name else ...)
            user_data.update(uncategorized_data)
        except UserDataError as e:
            raise UserUploadError(str(e))
        if user_data.profile_id and user_data.profile_id != old_profile_id:
            self.logger.add_info(UserChangeMessage.profile_info(user_data.profile_id, profile_name))

    def save_log(self):
        # Tracking for role is done post save to have role setup correctly on save
        if self.role_updated:
            new_role = self.user.get_role(domain=self.user_domain)
            self.logger.add_info(UserChangeMessage.role_change(new_role))

        self._include_user_data_changes()
        return self.logger.save()

    def _include_user_data_changes(self):
        new_user_data = self.user.get_user_data(self.user_domain).raw
        if self.logger.original_user_data != new_user_data:
            self.logger.add_changes({'user_data': new_user_data})


class CommCareUserImporter(BaseUserImporter):

    def update_phone_numbers(self, phone_numbers):
        """
        The first item in 'phone_numbers' will be the default
        """
        old_user_phone_numbers = self.user.phone_numbers
        fmt_phone_numbers = [_fmt_phone(n) for n in phone_numbers]

        if any(fmt_phone_numbers):
            self.user.set_phone_numbers(fmt_phone_numbers, default_number=fmt_phone_numbers[0])
        else:
            self.user.set_phone_numbers([])

        self._log_phone_number_changes(old_user_phone_numbers, fmt_phone_numbers)

    def update_name(self, name):
        self.user.set_full_name(str(name))
        self.logger.add_changes({'first_name': self.user.first_name, 'last_name': self.user.last_name})

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
            get_location_from_site_code,
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
                locations = [get_location_from_site_code(code, domain_info.location_cache)
                             for code in location_codes]
                self.logger.add_info(
                    UserChangeMessage.assigned_locations_info(locations))
            else:
                self.logger.add_info(UserChangeMessage.assigned_locations_info([]))

        # log this after assigned locations are updated, which can re-set primary location
        if self.user.location_id != user_current_primary_location_id:
            self.logger.add_changes({'location_id': self.user.location_id})
            if self.user.location_id:
                self.logger.add_info(
                    UserChangeMessage.primary_location_info(
                        self.user.get_sql_location(self.user_domain)
                    )
                )
            else:
                self.logger.add_info(UserChangeMessage.primary_location_removed())

    def update_user_groups(self, domain_info, group_names):
        """
        Add/remove user from groups without save and return change message for changes, if any
        """
        old_group_ids = set()
        for group in domain_info.group_memoizer.by_user_id(self.user.user_id):
            old_group_ids.add(group.get_id)
            if group.name not in group_names:
                group.remove_user(self.user)
                domain_info.group_memoizer.updated_groups.add(group.get_id)

        new_groups = {}
        for group_name in group_names:
            group = domain_info.group_memoizer.by_name(group_name)
            new_groups[group.get_id] = group
            if group.add_user(self.user, save=False):
                domain_info.group_memoizer.group_updated(group.get_id)

        if set(new_groups) != old_group_ids:
            return UserChangeMessage.groups_info(list(new_groups.values()))

    def update_deactivate_after(self, deactivate_after):
        change_message = DeactivateMobileWorkerTrigger.update_trigger(
            self.user_domain, self.user.user_id, deactivate_after
        )
        if change_message:
            self.logger.add_info(UserChangeMessage.updated_deactivate_after(
                deactivate_after, change_message
            ))

    def _log_phone_number_changes(self, old_phone_numbers, new_phone_numbers):
        (items_added, items_removed) = find_differences_in_list(
            target=new_phone_numbers,
            source=old_phone_numbers
        )

        change_messages = {}
        if items_added:
            change_messages.update(UserChangeMessage.phone_numbers_added(list(items_added))["phone_numbers"])

        if items_removed:
            change_messages.update(UserChangeMessage.phone_numbers_removed(list(items_removed))["phone_numbers"])

        if change_messages:
            self.logger.add_change_message({'phone_numbers': change_messages})


def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, str):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")


class WebUserImporter(BaseUserImporter):
    def add_to_domain(self, role_qualified_id, location_id):
        self.user.add_as_web_user(self.user_domain, role=role_qualified_id, location_id=location_id)
        self.role_updated = bool(role_qualified_id)

        self.logger.add_info(UserChangeMessage.added_as_web_user(self.user_domain))
        if location_id:
            self._log_primary_location_info()

    def _log_primary_location_info(self):
        primary_location = self.user.get_sql_location(self.user_domain)
        self.logger.add_info(UserChangeMessage.primary_location_info(primary_location))

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
                self.logger.add_info(UserChangeMessage.primary_location_removed())

    def update_locations(self, location_codes, membership, domain_info):
        from corehq.apps.user_importer.importer import (
            check_modified_user_loc,
            find_location_id,
            get_location_from_site_code,
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
            else:
                locations = []
            self.logger.add_info(UserChangeMessage.assigned_locations_info(locations))

        # log this after assigned locations are updated, which can re-set primary location
        user_updated_primary_location_id = get_user_primary_location_id(self.user, self.user_domain)
        if user_updated_primary_location_id != user_current_primary_location_id:
            if user_updated_primary_location_id:
                self._log_primary_location_info()
            else:
                self.logger.add_info(UserChangeMessage.primary_location_removed())


def get_user_primary_location_id(user, domain):
    primary_location = user.get_sql_location(domain)
    if primary_location:
        return primary_location.location_id


def get_user_primary_location_name(user, domain):
    primary_location = user.get_sql_location(domain)
    if primary_location:
        return primary_location.name


def find_differences_in_list(target: list, source: list):
    """
    Find the differences between 'source' and 'target' and
    return (added_items, removed_items)

    'added_items': items that are in 'target' but not in 'source'
    'removed_items': items that are in 'source' but not 'target'

    >>> find_differences_in_list(list_to_compare=[3,4,5,6], reference_list=[1,2,3,5])
    ({4, 6}, {1, 2})
    """

    shared_items = set(target).intersection(source)

    added_items = set(target).difference(shared_items)
    removed_items = set(source).difference(shared_items)

    return added_items, removed_items
