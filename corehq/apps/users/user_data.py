from django.utils.functional import cached_property

from corehq.apps.custom_data_fields.models import (
    COMMCARE_PROJECT,
    PROFILE_SLUG,
    CustomDataFieldsProfile,
)
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView


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

    def __repr__(self):
        return f"UserData({self.to_dict()})"

    @cached_property
    def profile(self):
        if self.profile_id:
            return self._get_profile(self.profile_id)

    def _get_profile(self, profile_id):
        return CustomDataFieldsProfile.objects.get(
            id=profile_id,
            definition__domain=self.domain,
            definition__field_type=UserFieldsView.field_type,
        )

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
            raise ValueError(f"'{key}' cannot be set directly")
        if key == PROFILE_SLUG:
            new_profile = self._get_profile(value)
            if set(new_profile.fields).intersection(set(self._local_to_user)):
                raise ValueError(f"Profile conflicts with existing data")
            del self.profile
        self._local_to_user[key] = value

    def update(self, data):
        original = self.to_dict()
        # set profile first to identify conflicts properly
        if PROFILE_SLUG in data:
            self[PROFILE_SLUG] = data[PROFILE_SLUG]
        for k, v in data.items():
            if k != PROFILE_SLUG:
                self[k] = v
        return original != self.to_dict()

    def __delitem__(self, key):
        if key in self._provided_by_system:
            raise ValueError(f"{key} cannot be deleted")
        if key == PROFILE_SLUG:
            del self.profile
        del self._local_to_user[key]
