from django.contrib.auth.models import User
from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from dimagi.utils.chunked import chunked

from corehq.apps.custom_data_fields.models import (
    COMMCARE_PROJECT,
    PROFILE_SLUG,
    CustomDataFieldsProfile,
    CustomDataFieldsDefinition,
    is_system_key,
)


class UserDataError(Exception):
    ...


class UserData:
    def __init__(self, raw_user_data, couch_user, domain, profile_id=None):
        self._local_to_user = raw_user_data
        self._couch_user = couch_user
        self.domain = domain
        self._profile_id = profile_id or raw_user_data.get(PROFILE_SLUG, None)

    @classmethod
    def for_user(cls, couch_user, domain):
        try:
            sql_data = SQLUserData.objects.get(
                user_id=couch_user.user_id,
                domain=domain,
            )
        except SQLUserData.DoesNotExist:
            return cls({}, couch_user, domain)

        return cls(sql_data.data, couch_user, domain, profile_id=sql_data.profile_id)

    @transaction.atomic
    def save(self):
        try:
            sql_data = (SQLUserData.objects
                        .select_for_update()
                        .get(user_id=self._couch_user.user_id, domain=self.domain))
        except SQLUserData.DoesNotExist:
            # Only create db object if there's something to persist
            if self._local_to_user or self.profile_id:
                SQLUserData.objects.create(
                    user_id=self._couch_user.user_id,
                    domain=self.domain,
                    data=self._local_to_user,
                    django_user=self._couch_user.get_django_user(),
                    profile_id=self.profile_id,
                )
        else:
            sql_data.data = self._local_to_user
            sql_data.profile_id = self.profile_id
            sql_data.save()

    @property
    def _provided_by_system(self):
        return {
            **(self.profile.fields if self.profile else {}),
            PROFILE_SLUG: self.profile_id or '',
            COMMCARE_PROJECT: self.domain,
        }

    def to_dict(self):
        return {
            **self._schema_defaults,
            **self._local_to_user,
            **self._provided_by_system,
        }

    @property
    def _schema_defaults(self):
        fields = self._schema_fields
        return {field.slug: '' for field in fields}

    @cached_property
    def _schema_fields(self):
        from corehq.apps.users.views.mobile.custom_data_fields import (
            CUSTOM_USER_DATA_FIELD_TYPE,
        )

        try:
            definition = CustomDataFieldsDefinition.objects.get(
                domain=self.domain, field_type=CUSTOM_USER_DATA_FIELD_TYPE)
            fields = definition.get_fields()
        except CustomDataFieldsDefinition.DoesNotExist:
            return []

        return fields

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

    @cached_property
    def profile(self):
        if self.profile_id:
            return self._get_profile(self.profile_id)

    def _get_profile(self, profile_id):
        from corehq.apps.users.views.mobile.custom_data_fields import (
            CUSTOM_USER_DATA_FIELD_TYPE,
        )
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


class SQLUserData(models.Model):
    domain = models.CharField(max_length=128)
    user_id = models.CharField(max_length=36)
    django_user = models.ForeignKey(User, on_delete=models.CASCADE)
    modified_on = models.DateTimeField(auto_now=True)

    profile = models.ForeignKey("custom_data_fields.CustomDataFieldsProfile",
                                on_delete=models.PROTECT, null=True)
    data = models.JSONField()

    class Meta:
        unique_together = ("user_id", "domain")
        indexes = [models.Index(fields=['user_id', 'domain'])]


def get_all_profiles_by_id(domain):
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE
    return {
        profile.id: profile for profile in CustomDataFieldsProfile.objects.filter(
            definition__domain=domain, definition__field_type=CUSTOM_USER_DATA_FIELD_TYPE)
    }


def get_user_schema_fields(domain):
    from corehq.apps.users.views.mobile.custom_data_fields import CUSTOM_USER_DATA_FIELD_TYPE

    try:
        definition = CustomDataFieldsDefinition.objects.get(domain=domain, field_type=CUSTOM_USER_DATA_FIELD_TYPE)
    except CustomDataFieldsDefinition.DoesNotExist:
        fields = []
    else:
        fields = definition.get_fields()
    return fields


def prime_user_data_caches(users, domain):
    """
    Enriches a set of users by looking up and priming user data caches in
    chunks, for use in bulk workflows.
    :return: generator that yields the enriched user objects
    """
    profiles_by_id = get_all_profiles_by_id(domain)
    schema_fields = get_user_schema_fields(domain)

    for chunk in chunked(users, 100):
        user_ids = [user.user_id for user in chunk]
        sql_data_by_user_id = {
            ud.user_id: ud for ud in
            SQLUserData.objects.filter(domain=domain, user_id__in=user_ids)
        }
        for user in chunk:
            if user.user_id in sql_data_by_user_id:
                sql_data = sql_data_by_user_id[user.user_id]
                user_data = UserData(sql_data.data, user, domain,
                                     profile_id=sql_data.profile_id)
            else:
                user_data = UserData({}, user, domain)
            # prime the user.get_user_data cache
            user._user_data_accessors[domain] = user_data

            # prime the user schema data to avoid individual database calls
            user_data._schema_fields = schema_fields
            if user_data.profile_id and user_data.profile_id in profiles_by_id:
                user_data.profile = profiles_by_id[user_data.profile_id]

            yield user
