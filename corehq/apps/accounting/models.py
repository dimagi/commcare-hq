from django.conf import settings
from django.db import models
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES


class BillingAccountType(object):
    CONTRACT = "CONTRACT"
    USER_CREATED = "USER_CREATED"
    CHOICES = (
        (CONTRACT, "Created by contract"),
        (USER_CREATED, "Created by user"),
    )






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


class BillingContact(models.Model):
    """
    This is the information we use to bill the client. It links to an existing WebUser
    by username, as WebUser currently lives in Couch.
    """
    web_user = models.CharField(max_length=80)
    phone_number = models.CharField(max_length=40)
    first_line = models.CharField(max_length=40)
    second_line = models.CharField(max_length=40, blank=True)
    city = models.CharField(max_length=40)
    state_province_region = models.CharField(max_length=40, blank=True)
    postal_code = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=40)


class BillingAccount(models.Model):
    """
    The key model that links a Subscription to its financial source and methods of payment.
    """
    name = models.CharField(max_length=40)
    salesforce_account_id = models.CharField(
        max_length=80,
        blank=True,
        help_text="This is the organization name in Salesforce",
    )
    created_by = models.CharField(max_length=80)
    date_created = models.DateField(auto_now_add=True)
    contact = models.ForeignKey(BillingContact, on_delete=models.PROTECT)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    is_auto_invoiceable = models.BooleanField(default=False)
    account_type = models.CharField(
        max_length=25,
        default=BillingAccountType.CONTRACT,
        choices=BillingAccountType.CHOICES,
    )

    @property
    def balance(self):
        # todo compute
        return 0.0
