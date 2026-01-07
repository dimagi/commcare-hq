from django.db import models
from django.utils.translation import gettext as _

from corehq.motech.models import ConnectionSettings


class MoMoEnvironments(models.TextChoices):
    SANDBOX = 'sandbox', _('Sandbox')
    LIVE = 'live', _('Live')


class MoMoProviders(models.TextChoices):
    MTN_MONEY = 'mtn_money', _('MTN Money')
    ORANGE_CAMEROON_MONEY = 'orange_cameroon_money', _('Orange Cameroon Money')


class MoMoConfig(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    provider = models.CharField(
        max_length=25,
        choices=MoMoProviders.choices,
        default=MoMoProviders.MTN_MONEY,
    )
    connection_settings = models.ForeignKey(
        ConnectionSettings, on_delete=models.PROTECT, null=True, blank=True,
    )
    environment = models.CharField(
        max_length=25, choices=MoMoEnvironments.choices, default=MoMoEnvironments.LIVE,
    )

    def get_payment_api_method(self):
        if self.provider == MoMoProviders.MTN_MONEY:
            from corehq.apps.integration.payments.services import make_mtn_payment_request
            return make_mtn_payment_request
        elif self.provider == MoMoProviders.ORANGE_CAMEROON_MONEY:
            from corehq.apps.integration.payments.services import make_orange_cameroon_payment_request
            return make_orange_cameroon_payment_request
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def get_payment_status_api_method(self):
        if self.provider == MoMoProviders.MTN_MONEY:
            from corehq.apps.integration.payments.services import make_mtn_payment_status_request
            return make_mtn_payment_status_request
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
