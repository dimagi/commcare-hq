from typing import Optional

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from corehq.apps.locations.models import SQLLocation

from dimagi.utils.couch.bulk import get_docs

from corehq.apps.api.exceptions import UpdateUserException
from corehq.apps.custom_data_fields.models import PROFILE_SLUG, CustomDataFieldsProfile
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.models import TableauAPISession
from corehq.apps.reports.util import get_tableau_groups_by_names, update_tableau_user
from corehq.apps.sms.util import strip_plus
from corehq.apps.user_importer.helpers import find_differences_in_list, UserChangeLogger
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.user_data import UserDataError
from corehq.apps.users.validation import validate_profile_required


class UserUpdates():
    def __init__(self, user, domain, user_change_logger: Optional[UserChangeLogger] = None):
        self.user = user
        self.domain = domain
        self.user_change_logger = user_change_logger

    def _update_user_data(self, new_user_data):
        try:
            profile_id = new_user_data.pop(PROFILE_SLUG, ...)
            changed = self.user.get_user_data(self.domain).update(new_user_data, profile_id=profile_id)
        except UserDataError as e:
            raise UpdateUserException(str(e))
        try:
            if profile_id != ... and profile_id is not None:
                profile = CustomDataFieldsProfile.objects.get(id=profile_id)
                if profile:
                    profile_name = profile.name
            else:
                profile_name = None
            validate_profile_required(profile_name, self.domain)
        except ValidationError as e:
            raise UpdateUserException(_(e.message))
        if self.user_change_logger and changed:
            self.user_change_logger.add_changes({
                'user_data': self.user.get_user_data(self.domain).raw
            }, skip_confirmation=True)

    def _update_user_role(self, role):
        roles = UserRole.objects.by_domain_and_name(self.domain, role)
        if not roles:
            raise UpdateUserException(_("The role '{}' does not exist").format(role))
        if len(roles) > 1:
            raise UpdateUserException(
                _("There are multiple roles with the name '{}' in the domain '{}'").format(role, self.domain)
            )

        original_role = self.user.get_role(self.domain)
        new_role = roles[0]
        if not original_role or original_role.get_qualified_id() != new_role.get_qualified_id():
            self.user.set_role(self.domain, new_role.get_qualified_id())
            if self.user_change_logger:
                self.user_change_logger.add_info(UserChangeMessage.role_change(new_role))

    def _update_location(self, location_object):
        primary_location_id = location_object.get('primary_location')
        location_ids = location_object.get('locations')

        if primary_location_id is None and location_ids is None:
            return

        current_primary_location_id = self.user.get_location_id(self.domain)
        current_locations = self.user.get_location_ids(self.domain)

        if not primary_location_id and not location_ids:
            self._remove_all_locations()
        else:
            if self._validate_locations(primary_location_id, location_ids):
                locations = self._verify_location_ids(location_ids)
                if primary_location_id != current_primary_location_id:
                    self._update_primary_location(primary_location_id)
                if set(current_locations) != set(location_ids):
                    self._update_assigned_locations(locations, location_ids)

    @classmethod
    def _validate_locations(cls, primary_location_id, location_ids):
        if not primary_location_id and not location_ids:
            return False
        if not primary_location_id or not location_ids:
            raise UpdateUserException(_('Both primary_location and locations must be provided together.'))
        if primary_location_id not in location_ids:
            raise UpdateUserException(_('Primary location must be included in the list of locations.'))
        return True

    def _remove_all_locations(self):
        self._unset_location()
        self._reset_locations([])
        if self.user_change_logger:
            self.user_change_logger.add_changes({'location_id': None})
            self.user_change_logger.add_info(UserChangeMessage.primary_location_removed())
            self.user_change_logger.add_changes({'assigned_location_ids': []})
            self.user_change_logger.add_info(UserChangeMessage.assigned_locations_info([]))

    def _update_primary_location(self, primary_location_id):
        primary_location = SQLLocation.active_objects.get(location_id=primary_location_id)
        self._set_location(primary_location)
        if self.user_change_logger:
            self.user_change_logger.add_changes({'location_id': primary_location_id})
            self.user_change_logger.add_info(UserChangeMessage.primary_location_info(primary_location))

    def _verify_location_ids(self, location_ids):
        locations = SQLLocation.active_objects.filter(location_id__in=location_ids, domain=self.domain)
        real_ids = [loc.location_id for loc in locations]

        if missing_ids := set(location_ids) - set(real_ids):
            raise UpdateUserException(f"Could not find location ids: {', '.join(missing_ids)}.")

        return locations

    def _update_assigned_locations(self, locations, location_ids):
        self._reset_locations(location_ids)
        if self.user_change_logger:
            self.user_change_logger.add_changes({'assigned_location_ids': location_ids})
            self.user_change_logger.add_info(UserChangeMessage.assigned_locations_info(locations))

    def _set_location(self, primary_location):
        raise NotImplementedError("Subclasses must implement reset_locations method")

    def _unset_location(self):
        raise NotImplementedError("Subclasses must implement reset_locations method")

    def _reset_locations(self, location_ids):
        raise NotImplementedError("Subclasses must implement reset_locations method")


class CommcareUserUpdates(UserUpdates):

    def update(self, field, value):
        """
        Used to update user fields via the API
        Raises exceptions if errors are encountered, otherwise the update is successful
        :param field: the attribute on the user to update
        :param value: the value to update the attribute to
        """
        update_fn = {
            'default_phone_number': self._update_default_phone_number,
            'email': self._update_email,
            'first_name': self._update_first_name,
            'groups': self._update_groups,
            'language': self._update_language,
            'last_name': self._update_last_name,
            'password': self._update_password,
            'phone_numbers': self._update_phone_numbers,
            'user_data': self._update_user_data,
            'role': self._update_user_role,
            'location': self._update_location,
        }.get(field)

        if not update_fn:
            raise UpdateUserException(_("Attempted to update unknown or non-editable field '{}'").format(field))

        update_fn(value)

    def _update_email(self, email):
        self._simple_update('email', email.lower())

    def _update_first_name(self, first_name):
        self._simple_update('first_name', first_name)

    def _update_last_name(self, last_name):
        self._simple_update('last_name', last_name)

    def _update_language(self, language):
        self._simple_update('language', language)

    def _simple_update(self, key, value):
        if getattr(self.user, key) != value:
            setattr(self.user, key, value)
            if self.user_change_logger:
                self.user_change_logger.add_changes({key: value})

    def _update_password(self, password):
        domain = Domain.get_by_name(self.domain)
        if domain.strong_mobile_passwords:
            try:
                clean_password(password)
            except ValidationError:
                raise UpdateUserException(_("Password is not strong enough."))
        self.user.set_password(password)

        if self.user_change_logger:
            self.user_change_logger.add_change_message(UserChangeMessage.password_reset())

    def _update_groups(self, group_ids):
        groups_updated = self.user.set_groups(group_ids)
        if self.user_change_logger and groups_updated:
            groups = []
            if group_ids:
                groups = [Group.wrap(doc) for doc in get_docs(Group.get_db(), group_ids)]
            self.user_change_logger.add_info(UserChangeMessage.groups_info(groups))

    def _update_default_phone_number(self, phone_number):
        old_phone_numbers = set(self.user.phone_numbers)
        new_phone_numbers = set(self.user.phone_numbers)
        if not isinstance(phone_number, str):
            raise UpdateUserException(_("'default_phone_number' must be a string"))
        formatted_phone_number = strip_plus(phone_number)
        new_phone_numbers.add(formatted_phone_number)
        self.user.set_default_phone_number(formatted_phone_number)

        if self.user_change_logger:
            self._log_phone_number_change(new_phone_numbers, old_phone_numbers)

    def _update_phone_numbers(self, phone_numbers):
        old_phone_numbers = set(self.user.phone_numbers)
        new_phone_numbers = set()
        self.user.phone_numbers = []
        for idx, phone_number in enumerate(phone_numbers):
            formatted_phone_number = strip_plus(phone_number)
            new_phone_numbers.add(formatted_phone_number)
            self.user.add_phone_number(formatted_phone_number)
            if idx == 0:
                self.user.set_default_phone_number(formatted_phone_number)

        if self.user_change_logger:
            self._log_phone_number_change(new_phone_numbers, old_phone_numbers)

    def _log_phone_number_change(self, new_phone_numbers, old_phone_numbers):
        numbers_added, numbers_removed = find_differences_in_list(
            target=list(new_phone_numbers),
            source=list(old_phone_numbers)
        )

        change_messages = {}
        if numbers_removed:
            change_messages.update(
                UserChangeMessage.phone_numbers_removed(list(numbers_removed))["phone_numbers"]
            )

        if numbers_added:
            change_messages.update(
                UserChangeMessage.phone_numbers_added(list(numbers_added))["phone_numbers"]
            )

        if change_messages:
            self.user_change_logger.add_change_message({'phone_numbers': change_messages})

    def _set_location(self, primary_location):
        self.user.set_location(primary_location, commit=False)

    def _unset_location(self):
        self.user.unset_location(commit=False)

    def _reset_locations(self, location_ids):
        self.user.reset_locations(location_ids, commit=False)


class WebUserUpdates(UserUpdates):

    def __init__(self, user, domain, keys_to_update=None, user_change_logger=None):
        super().__init__(user, domain, user_change_logger)
        self._tableau_session = None
        self.keys_to_update = keys_to_update

    def update(self, field, value):
        """
        Used to update user fields via the API
        Raises exceptions if errors are encountered, otherwise the update is successful
        :param field: the attribute on the user to update
        :param value: the value to update the attribute to
        """
        update_fn = {
            'role': self._update_user_role,
            'location': self._update_location,
            'user_data': self._update_user_data,
            'tableau_role': self._update_tableau_role,
            'tableau_groups': self._update_tableau_groups,
        }.get(field)

        if not update_fn:
            raise UpdateUserException(_("Attempted to update unknown or non-editable field '{}'").format(field))
        update_fn(value)

    @property
    def tableau_session(self):
        if self._tableau_session is None and (
            'tableau_role' in self.keys_to_update or 'tableau_groups' in self.keys_to_update
        ):
            self._tableau_session = TableauAPISession.create_session_for_domain(self.domain)
        return self._tableau_session

    def _update_tableau_role(self, tableau_role):
        update_tableau_user(self.domain, self.user.username, tableau_role, session=self.tableau_session)

    def _update_tableau_groups(self, tableau_group_names):
        tableau_groups = get_tableau_groups_by_names(tableau_group_names, self.domain)
        update_tableau_user(self.domain, self.user.username, groups=tableau_groups, session=self.tableau_session)

    def _set_location(self, primary_location):
        self.user.set_location(self.domain, primary_location, commit=False)

    def _unset_location(self):
        self.user.unset_location(self.domain, commit=False)

    def _reset_locations(self, location_ids):
        self.user.reset_locations(self.domain, location_ids, commit=False)
