from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _

import jsonfield

from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.integration.kyc.exceptions import UserCaseNotFound
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.motech.const import OAUTH2_CLIENT
from corehq.motech.models import ConnectionSettings


class UserDataStore(object):
    CUSTOM_USER_DATA = 'custom_user_data'
    USER_CASE = 'user_case'
    OTHER_CASE_TYPE = 'other_case_type'
    CHOICES = [
        (CUSTOM_USER_DATA, _('Custom User Data')),
        (USER_CASE, _('User Case')),
        (OTHER_CASE_TYPE, _('Other Case Type')),
    ]


class KycProviders(models.TextChoices):
    # When adding a new provider:
    # 1. Add connection settings to `settings.py` if necessary
    # 2. Add it to `KycConfig.get_connections_settings()`
    MTN_KYC = 'mtn_kyc', _('MTN KYC')


class KycConfig(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    user_data_store = models.CharField(max_length=25, choices=UserDataStore.CHOICES)
    other_case_type = models.CharField(max_length=126, null=True)
    api_field_to_user_data_map = jsonfield.JSONField(default=dict)
    provider = models.CharField(
        max_length=25,
        choices=KycProviders.choices,
        default=KycProviders.MTN_KYC,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['domain', 'provider'], name='unique_domain_provider'),
        ]

    def clean(self):
        super().clean()
        if (
            self.user_data_store == UserDataStore.OTHER_CASE_TYPE
            and not self.other_case_type
        ):
            raise ValidationError({
                'other_case_type': _(
                    'This field is required when "Recipient Data Store" is set to '
                    '"Other Case Type".'
                )
            })
        elif self.user_data_store != UserDataStore.OTHER_CASE_TYPE:
            self.other_case_type = None

    def get_connection_settings(self):
        if self.provider == KycProviders.MTN_KYC:
            kyc_settings = settings.MTN_KYC_CONNECTION_SETTINGS
            return ConnectionSettings(
                domain=self.domain,
                name=KycProviders.MTN_KYC.label,
                url=kyc_settings['url'],
                auth_type=OAUTH2_CLIENT,
                client_id=kyc_settings['client_id'],
                client_secret=kyc_settings['client_secret'],
                token_url=kyc_settings['token_url'],
            )
        # elif self.provider == KycProviders.NEW_PROVIDER_HERE: ...
        else:
            raise ValueError(f'Unable to determine connection settings for KYC provider {self.provider!r}.')

    def get_kyc_users(self):
        """
        Returns all CommCareUser or CommCareCase instances based on the
        user data store.
        """
        if self.user_data_store in (
            UserDataStore.CUSTOM_USER_DATA,
            UserDataStore.USER_CASE,
        ):
            return [
                KycUser(self, user_obj)
                for user_obj in CommCareUser.by_domain(self.domain)
            ]
        elif self.user_data_store == UserDataStore.OTHER_CASE_TYPE:
            assert self.other_case_type
            case_ids = (
                CaseSearchES()
                .domain(self.domain)
                .case_type(self.other_case_type)
            ).get_ids()
            if not case_ids:
                return []
            return [
                KycUser(self, user_obj)
                for user_obj in CommCareCase.objects.get_cases(case_ids, self.domain)
            ]

    def get_kyc_users_by_ids(self, obj_ids):
        """
        Returns all CommCareUser or CommCareCase instances based on the
        user data store and user IDs.
        """
        if self.user_data_store in (
            UserDataStore.CUSTOM_USER_DATA,
            UserDataStore.USER_CASE,
        ):
            user_objs = [CommCareUser.get_by_user_id(id_) for id_ in obj_ids]
            return [KycUser(self, user_obj) for user_obj in user_objs]
        elif self.user_data_store == UserDataStore.OTHER_CASE_TYPE:
            assert self.other_case_type
            return [
                KycUser(self, user_obj)
                for user_obj in CommCareCase.objects.get_cases(obj_ids, self.domain)
            ]


class KycUser:

    # CommCareUser properties that could map to API fields
    safe_commcare_user_properties = {
        'first_name',
        'last_name',
        'full_name',
        'name',
        'email',
        'username',  # For CommCareUsers this is an email address
        'phone_number',
        'default_phone_number',
    }

    def __init__(self, kyc_config, user_or_case_obj):
        """
        :param kyc_config: kyc configuration for the domain
        :param user_or_case_obj: can be an instance of 'CommcareUser' or 'CommcareCase' based on the configuration.
        """
        self.kyc_config = kyc_config
        self._user_or_case_obj = user_or_case_obj
        if isinstance(self._user_or_case_obj, CommCareUser):
            self.user_id = self._user_or_case_obj.user_id
        else:
            self.user_id = self._user_or_case_obj.case_id
        self._user_data = None

    def __getitem__(self, item):
        """
        Allow user data to be accessible like a dictionary.
        """
        if item in self.user_data:
            # Fetch value from usercase / custom user data by default
            return self.user_data[item]
        if (
            isinstance(self._user_or_case_obj, CommCareUser)
            and item in self.safe_commcare_user_properties
        ):
            # Fall back to CommCareUser
            return getattr(self._user_or_case_obj, item)
        else:
            raise KeyError(item)

    @property
    def user_data(self):
        if self._user_data is None:
            if self.kyc_config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
                self._user_data = self._user_or_case_obj.get_user_data(self.kyc_config.domain).to_dict()
            elif self.kyc_config.user_data_store == UserDataStore.USER_CASE:
                custom_user_case = self._user_or_case_obj.get_usercase()
                if not custom_user_case:
                    raise UserCaseNotFound("User case not found for the user.")
                self._user_data = custom_user_case.case_json
            else:  # UserDataStore.OTHER_CASE_TYPE
                self._user_data = self._user_or_case_obj.case_json
        return self._user_data

    @property
    def kyc_last_verified_at(self):
        return self.user_data.get('kyc_last_verified_at')

    @property
    def kyc_verification_status(self):
        value = self.user_data.get('kyc_verification_status')
        # value can be '' when field is defined as a custom field in custom user data
        assert value in (
            KycVerificationStatus.PENDING,
            KycVerificationStatus.PASSED,
            KycVerificationStatus.FAILED,
            ''
        )
        return value or KycVerificationStatus.PENDING

    @property
    def kyc_provider(self):
        return self.user_data.get('kyc_provider')

    def update_verification_status(self, verification_status, device_id=None):
        from corehq.apps.hqcase.utils import update_case

        assert verification_status in [KycVerificationStatus.PASSED, KycVerificationStatus.FAILED]
        update = {
            'kyc_provider': self.kyc_config.provider,
            'kyc_last_verified_at': datetime.utcnow().isoformat(),  # TODO: UTC or project timezone?
            'kyc_verification_status': verification_status,
        }
        if self.kyc_config.user_data_store == UserDataStore.CUSTOM_USER_DATA:
            user_data_obj = self._user_or_case_obj.get_user_data(self.kyc_config.domain)
            user_data_obj.update(update)
            user_data_obj.save()
        else:
            if isinstance(self._user_or_case_obj, CommCareUser):
                case_id = self._user_or_case_obj.get_usercase().case_id
            else:
                case_id = self._user_or_case_obj.case_id
            update_case(
                self.kyc_config.domain,
                case_id,
                case_properties=update,
                device_id=device_id or f'{__name__}.update_status',
            )
            if isinstance(self._user_or_case_obj, CommCareCase):
                self._user_or_case_obj.refresh_from_db()
        self._user_data = None


class KycVerificationStatus:
    PASSED = 'passed'
    # FAILED indicates a request was made to KYC Provider and the KYC failed
    FAILED = 'failed'
    # PENDING indicates KYC is yet to be initiated and in that case, verification status is returned as None
    # as case property/field does not exist or is empty.
    PENDING = None


class KycVerificationFailureCause(models.TextChoices):
    USER_INFORMATION_INCOMPLETE = (
        'user_information_incomplete', _("User information on HQ is not complete or invalid.")
    )
    USER_INFORMATION_MISMATCH = (
        'user_information_mismatch', _("User information on HQ does not match with KYC provider.")
    )
    NETWORK_ERROR = ('network_error', _("Network error occurred. Please reach out to support."))
    API_ERROR = ('api_error', _("API error occurred. Please reach out to support."))
