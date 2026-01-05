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
