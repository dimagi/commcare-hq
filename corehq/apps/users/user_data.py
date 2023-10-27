from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from corehq.apps.custom_data_fields.models import (
    COMMCARE_PROJECT,
    PROFILE_SLUG,
    CustomDataFieldsProfile,
    is_system_key,
)
from corehq.apps.users.views.mobile.custom_data_fields import (
    CUSTOM_USER_DATA_FIELD_TYPE,
)


class UserDataError(Exception):
    ...


class UserData:
    def __init__(self, raw_user_data, domain, profile_id=None):
        self._local_to_user = raw_user_data
        self.domain = domain
        self._profile_id = profile_id or raw_user_data.get(PROFILE_SLUG, None)

    @property
    def _provided_by_system(self):
        return {
            **(self.profile.fields if self.profile else {}),
            PROFILE_SLUG: self.profile_id or '',
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

    @property
    def profile_id(self):
        return self._profile_id

    @profile_id.setter
    def profile_id(self, profile_id):
        try:
            del self.profile
        except AttributeError:
            pass
        if profile_id:
            new_profile = self._get_profile(profile_id)
            non_empty_existing_fields = {k for k, v in self._local_to_user.items() if v}
            if set(new_profile.fields).intersection(non_empty_existing_fields):
                raise UserDataError(_("Profile conflicts with existing data"))
        self._profile_id = profile_id
        self._local_to_user[PROFILE_SLUG] = profile_id

    @cached_property
    def profile(self):
        if self.profile_id:
            return self._get_profile(self.profile_id)

    def _get_profile(self, profile_id):
        try:
            return CustomDataFieldsProfile.objects.get(
                id=profile_id,
                definition__domain=self.domain,
                definition__field_type=CUSTOM_USER_DATA_FIELD_TYPE,
            )
        except CustomDataFieldsProfile.DoesNotExist as e:
            raise UserDataError(_("User data profile not found")) from e

    def remove_unrecognized(self, schema_fields):
        changed = False
        for k in list(self._local_to_user):
            if k not in schema_fields and not is_system_key(k):
                del self[k]
                changed = True
        return changed

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
            raise UserDataError(_("'{}' cannot be set directly").format(key))
        if key == PROFILE_SLUG:
            # TODO disallow
            self.profile_id = value
        self._local_to_user[key] = value

    def update(self, data, profile_id=...):
        # There are order-specific conflicts that can arise when setting values
        # individually - this method is a monolithic action whose final state
        # should be consistent
        original = self.to_dict()
        original_profile = self.profile_id
        for k in data:
            self._local_to_user.pop(k, None)
        if PROFILE_SLUG in data:
            self.profile_id = data[PROFILE_SLUG]
        if profile_id != ...:
            self.profile_id = profile_id
        for k, v in data.items():
            if k != PROFILE_SLUG:
                if v or k not in self._provided_by_system:
                    self[k] = v
        return original != self.to_dict() or original_profile != self.profile_id

    def __delitem__(self, key):
        if key in self._provided_by_system:
            raise UserDataError(_("{} cannot be deleted").format(key))
        if key == PROFILE_SLUG:
            # TODO disallow
            self.profile_id = None
        del self._local_to_user[key]

    def pop(self, key, default=...):
        try:
            ret = self._local_to_user[key]
        except KeyError as e:
            if key in self._provided_by_system:
                raise UserDataError(_("{} cannot be deleted").format(key)) from e
            if default != ...:
                return default
            raise e
        else:
            del self._local_to_user[key]
            return ret

    def save(self):
        # TODO
        ...
