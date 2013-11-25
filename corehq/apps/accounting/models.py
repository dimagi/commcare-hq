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


class FeatureType(object):
    USER = "USER"
    SMS = "SMS"
    API = "API"
    CHOICES = (
        (USER, "Users"),
        (SMS, "SMS"),
        (API, "API"),
    )


class SoftwareProductType(object):
    COMMCARE = "CommCare"
    COMMTRACK = "CommTrack"
    COMMCONNECT = "CommConnect"
    CHOICES = (
        (COMMCARE, "CommCare"),
        (COMMTRACK, "CommTrack"),
        (COMMCONNECT, "CommConnect"),
    )


class SoftwarePlanVisibility(object):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CHOICES = (
        (PUBLIC, "Anyone can subscribe"),
        (INTERNAL, "Dimagi must create subscription"),
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


class BillingAccount(models.Model):
    """
    The key model that links a Subscription to its financial source and methods of payment.
    """
    name = models.CharField(max_length=40, db_index=True)
    salesforce_account_id = models.CharField(
        db_index=True,
        max_length=80,
        blank=True,
        help_text="This is how we link to the salesforce account",
    )
    created_by = models.CharField(max_length=80)
    date_created = models.DateField(auto_now_add=True)
    web_user_contact = models.CharField(max_length=80)
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


class SoftwareProduct(models.Model):
    """
    Specifies a product name that can be included in a subscription. e.g. CommTrack Pro, CommCare Community, etc.
    """
    name = models.CharField(max_length=40, unique=True)
    product_type = models.CharField(max_length=10, db_index=True, choices=SoftwareProductType.CHOICES)


class SoftwareProductRate(models.Model):
    """
    Links a SoftwareProduct to a monthly fee.
    Once created, ProductRates cannot be modified. Instead, a new ProductRate must be created.
    """
    product = models.ForeignKey(SoftwareProduct, on_delete=models.PROTECT)
    monthly_fee = models.FloatField()
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class Feature(models.Model):
    """
    This is what will link a feature type (USER, API, etc.) to a name (Users Pro, API Standard, etc.) and will be what
    the FeatureRate references to provide a monthly fee, limit and per-excess fee.
    """
    name = models.CharField(max_length=40, unique=True)
    feature_type = models.CharField(max_length=10, db_index=True, choices=FeatureType.CHOICES)


class FeatureRate(models.Model):
    """
    Links a feature to a monthly fee, monthly limit, and a per-excess fee for exceeding the monthly limit.
    Once created, Feature Rates cannot be modified. Instead, a new Feature Rate must be created.
    """
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT)
    monthly_fee = models.FloatField(default=0.0)
    monthly_limit = models.IntegerField(default=0)
    per_excess_fee = models.FloatField(default=0.0)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class SoftwarePlan(models.Model):
    """
    Subscriptions are created for Software Plans. Software Plans can have many Software Plan Versions, which
    link the Software Plan to a set of permissions roles.
    """
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField()
    visibility = models.CharField(
        max_length=10,
        default=SoftwarePlanVisibility.INTERNAL,
        choices=SoftwarePlanVisibility.CHOICES,
    )


class SoftwarePlanVersion(models.Model):
    """
    Links a plan to its rates and provides versioning information.
    Once a new SoftwarePlanVersion is created, it cannot be modified. Instead, a new SofwarePlanVersion
    must be created.
    """
    plan = models.ForeignKey(SoftwarePlan, on_delete=models.PROTECT)
    product_rates = models.ManyToManyField(SoftwareProductRate, blank=True)
    feature_rates = models.ManyToManyField(FeatureRate, blank=True)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class Subscriber(models.Model):
    """
    The objects that can be subscribed to a Subscription.
    """
    domain = models.CharField(max_length=25, null=True, db_index=True)
    organization = models.CharField(max_length=25, null=True, db_index=True)


class Subscription(models.Model):
    """
    Links a Subscriber to a SoftwarePlan and BillingAccount, necessary for invoicing.
    """
    account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT)
    plan = models.ForeignKey(SoftwarePlanVersion, on_delete=models.PROTECT)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.PROTECT)
    # todo: hook in roles = models.ForeignKey(Roles)
    salesforce_contract_id = models.CharField(blank=True, max_length=80)
    date_start = models.DateField()
    date_end = models.DateField(blank=True)
    date_delay_invoicing = models.DateField(blank=True)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=False)
