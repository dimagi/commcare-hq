from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class HQAccountingSetupError(Exception):
    pass


class Currency(models.Model):
    """
    Keeps track of the current conversion rates so that we don't have to poll the free, but rate limited API
    from Open Exchange Rates. Necessary for billing things like MACH SMS.
    """
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=25, db_index=True)
    symbol = models.CharField(max_length=10)
    rate_to_usd = models.DecimalField(default=1.0, max_digits=10, decimal_places=9)
    date_updated = models.DateField(auto_now=True)

    @classmethod
    def get_default(cls):
        try:
            return cls.objects.get(code=settings.DEFAULT_CURRENCY)
        except ObjectDoesNotExist:
            raise HQAccountingSetupError("You need initialize a default currency. Your current default is set to: %s"
                                         % settings.DEFAULT_CURRENCY)
