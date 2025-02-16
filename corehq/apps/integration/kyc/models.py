from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _

import jsonfield

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
    api_field_to_user_data_map = jsonfield.JSONField(default=list)
    provider = models.CharField(
        max_length=25,
        choices=KycProviders.choices,
        default=KycProviders.MTN_KYC,
    )
    connection_settings = models.ForeignKey(
        ConnectionSettings,
        on_delete=models.PROTECT,
        # Assumes we can determine connection settings for provider
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['domain', 'provider'], name='unique_domain_provider'),
        ]

    def get_connection_settings(self):
        if not self.connection_settings_id:
            if self.provider == KycProviders.MTN_KYC:
                kyc_settings = settings.MTN_KYC_CONNECTION_SETTINGS
                self.connection_settings = ConnectionSettings.objects.create(
                    domain=self.domain,
                    name=KycProviders.MTN_KYC.label,
                    url=kyc_settings['url'],
                    auth_type=OAUTH2_CLIENT,
                    client_id=kyc_settings['client_id'],
                    client_secret=kyc_settings['client_secret'],
                    token_url=kyc_settings['token_url'],
                )
                self.save()
            # elif self.provider == KycProviders.NEW_PROVIDER_HERE: ...
            else:
                raise ValueError(f'Unable to determine connection settings for KYC provider {self.provider!r}.')
        return self.connection_settings
