from django.utils.functional import cached_property

from corehq.apps.custom_data_fields.models import (
    COMMCARE_PROJECT,
    PROFILE_SLUG,
    CustomDataFieldsProfile,
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


class UserDataError(Exception):
    ...


class UserData:
    def __init__(self, raw_user_data, domain):
        self._local_to_user = raw_user_data
        self.domain = domain

    @property
    def profile_id(self):
        return self._local_to_user.get(PROFILE_SLUG)

    @property
    def _provided_by_system(self):
        return {
            **(self.profile.fields if self.profile else {}),
            COMMCARE_PROJECT: self.domain,
        }

    def to_dict(self):
        return {
            **self._local_to_user,
            **self._provided_by_system,
        }

    @property
    def raw(self):
        """Data stored on the user object - used for auditing"""
        return self._local_to_user.copy()

    def __repr__(self):
        return f"UserData({self.to_dict()})"

    @cached_property
    def profile(self):
        if self.profile_id:
            return self._get_profile(self.profile_id)

    def _get_profile(self, profile_id):
        try:
            return CustomDataFieldsProfile.objects.get(
                id=profile_id,
                definition__domain=self.domain,
                definition__field_type=UserFieldsView.field_type,
            )
        except CustomDataFieldsProfile.DoesNotExist as e:
            raise UserDataError("User data profile not found") from e

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __getitem__(self, key):
        return self.to_dict()[key]

    def __contains__(self, item):
        return item in self.to_dict()

    def get(self, key, default=None):
        return self.to_dict().get(key, default)

    def __setitem__(self, key, value):
        if key in self._provided_by_system:
            if value == self._provided_by_system[key]:
                return
            raise UserDataError(f"'{key}' cannot be set directly")
        if key == PROFILE_SLUG:
            del self.profile
            if not value:
                self._local_to_user.pop(PROFILE_SLUG, None)
                return
            new_profile = self._get_profile(value)
            non_empty_existing_fields = {k for k, v in self._local_to_user.items() if v}
            if set(new_profile.fields).intersection(non_empty_existing_fields):
                raise UserDataError("Profile conflicts with existing data")
        self._local_to_user[key] = value

    def update(self, data):
        # There are order-specific conflicts that can arise when setting values
        # individually - this method is a monolithic action whose final state
        # should be consistent
        original = self.to_dict()
        for k in data:
            self._local_to_user.pop(k, None)
        if PROFILE_SLUG in data:
            self[PROFILE_SLUG] = data[PROFILE_SLUG]
        for k, v in data.items():
            if k != PROFILE_SLUG:
                if v or k not in self._provided_by_system:
                    self[k] = v
        return original != self.to_dict()

    def __delitem__(self, key):
        if key in self._provided_by_system:
            raise UserDataError(f"{key} cannot be deleted")
        if key == PROFILE_SLUG:
            del self.profile
        del self._local_to_user[key]

    def pop(self, key, default=...):
        try:
            ret = self._local_to_user[key]
        except KeyError as e:
            if key in self._provided_by_system:
                raise UserDataError(f"{key} cannot be deleted") from e
            if default != ...:
                return default
            raise e
        else:
            del self._local_to_user[key]
            return ret
