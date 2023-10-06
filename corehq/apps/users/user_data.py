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
        self.profile_id = raw_user_data.get(PROFILE_SLUG)
        self.domain = domain

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
            return CustomDataFieldsProfile.objects.get(
                id=self.profile_id,
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
            del self.profile
        self._local_to_user[key] = value

    def update(self, data):
        for k, v in data.items():
            self[k] = v

    def __delitem__(self, key):
        if key in self._provided_by_system:
            raise ValueError(f"{key} cannot be deleted")
        if key == PROFILE_SLUG:
            del self.profile
        del self._local_to_user[key]
