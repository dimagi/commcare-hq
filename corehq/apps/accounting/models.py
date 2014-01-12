from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from corehq.apps.accounting.exceptions import HQAccountingSetupError
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES


class Currency(models.Model):
    """
    Keeps track of the current conversion rates so that we don't have to poll the free, but rate limited API
    from Open Exchange Rates. Necessary for billing things like MACH SMS.
    """
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=25, db_index=True)
    symbol = models.CharField(max_length=10)
    rate_to_default = models.DecimalField(default=1.0, max_digits=20, decimal_places=EXCHANGE_RATE_DECIMAL_PLACES)
    date_updated = models.DateField(auto_now=True)

    @classmethod
    def get_default(cls):
        default, _ = Currency.objects.get_or_create(code=settings.DEFAULT_CURRENCY)
        return default
