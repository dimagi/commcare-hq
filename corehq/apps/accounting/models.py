import datetime
from decimal import Decimal

from couchdbkit.ext.django.schema import DateTimeProperty, StringProperty

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES

from django_prbac.models import Role
from dimagi.utils.couch.database import SafeSaveDocument
from dimagi.utils.decorators.memoized import memoized


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

class AdjustmentReason(object):
    DIRECT_PAYMENT = "DIRECT_PAYMENT"
    SALESFORCE = "SALESFORCE"
    INVOICE = "INVOICE"
    MANUAL = "MANUAL"
    CHOICES = (
        (MANUAL, "manual"),
        (SALESFORCE, "via Salesforce"),
        (INVOICE, "invoice generated"),
        (DIRECT_PAYMENT, "payment from client received"),
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
    monthly_fee = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=2)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def new_rate(cls, product_name, monthly_fee, save=True):
        product, _ = SoftwareProduct.objects.get_or_create(name=product_name)
        rate = SoftwareProductRate(product=product, monthly_fee=monthly_fee)
        if save:
            rate.save()
        return rate


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
    monthly_fee = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=2)
    monthly_limit = models.IntegerField(default=0)
    per_excess_fee = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=2)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def new_rate(cls, feature_name, feature_type,
                 monthly_fee=None, monthly_limit=None, per_excess_fee=None, save=True):
        feature, _ = Feature.objects.get_or_create(name=feature_name, feature_type=feature_type)
        rate = FeatureRate(feature=feature)

        if monthly_fee is not None:
            rate.monthly_fee = monthly_fee
        if monthly_limit is not None:
            rate.monthly_limit = monthly_limit
        if per_excess_fee is not None:
            rate.per_excess_fee = per_excess_fee

        if save:
            rate.save()
        return rate


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
    role = models.ForeignKey(Role, null=True)  # null=True will be removed once this and PRBAC are fully synced


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
    salesforce_contract_id = models.CharField(blank=True, max_length=80)
    date_start = models.DateField()
    date_end = models.DateField(blank=True, null=True)
    date_delay_invoicing = models.DateField(blank=True, null=True)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=False)


class Invoice(models.Model):
    """
    This is what we'll use to calculate the balance on the accounts based on the current balance
    held by the Invoice. Balance updates will be tied to CreditAdjustmentTriggers which are tied
    to CreditAdjustments.
    """
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT)
    tax_rate = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=4)
    balance = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=4)
    date_due = models.DateField(db_index=True)
    date_paid = models.DateField(blank=True, null=True)
    date_created = models.DateField(auto_now_add=True)
    date_received = models.DateField(blank=True, db_index=True, null=True)
    date_start = models.DateField()
    date_end = models.DateField()

    @property
    @memoized
    def subtotal(self):
        """
        This will be inserted in the subtotal field on the printed invoice.
        """
        if self.lineitem_set.count() == 0:
            return Decimal('0.0')
        return sum([line_item.total for line_item in self.lineitem_set.all()])

    @property
    def applied_tax(self):
        return self.tax_rate * self.subtotal

    @property
    def applied_credit(self):
        if self.creditadjustment_set.count() == 0:
            return Decimal('0.0')
        return sum([credit.amount for credit in self.creditadjustment_set.all()])

    def get_total(self):
        """
        This will be inserted in the total field on the printed invoice.
        """
        return self.subtotal + self.applied_tax + self.applied_credit

    def update_balance(self):
        self.balance = self.get_total()

    def calculate_credit_adjustments(self):
        """
        This goes through all credit lines that:
        - do not have feature/product rates, but specify the related subscription and billing account
        - do not have feature/product rates or a subscription, but specify the related billing account
        """
        # todo: implement
        pass


class BillingRecord(models.Model):
    """
    This stores any interaction we have with the client in sending a physical / pdf invoice to their contact email.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT)
    date_emailed = models.DateField(auto_now_add=True, db_index=True)
    emailed_to = models.CharField(max_length=254, db_index=True)
    pdf_data_id = models.CharField(max_length=48)

    @property
    def pdf(self):
        return InvoicePdf.get(self.pdf_data_id)


class InvoicePdf(SafeSaveDocument):
    invoice_id = StringProperty()
    date_created = DateTimeProperty()

    def generate_pdf(self, invoice):
        # todo generate pdf
        invoice.pdf_data_id = self._id
        # self.put_attachment(pdf_data)
        self.invoice_id = invoice.id
        self.date_created = datetime.datetime.now()


class LineItemManager(models.Manager):
    def get_products(self):
        return self.get_query_set().filter(feature_rate__exact=None)

    def get_features(self):
        return self.get_query_set().filter(product_rate__exact=None)

    def get_feature_by_type(self, feature_type):
        return self.get_query_set().filter(feature_rate__feature__feature_type=feature_type)


class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT)
    feature_rate = models.ForeignKey(FeatureRate, on_delete=models.PROTECT, null=True)
    product_rate = models.ForeignKey(SoftwareProductRate, on_delete=models.PROTECT, null=True)
    base_description = models.TextField(blank=True, null=True)
    base_cost = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=2)
    unit_description = models.TextField(blank=True, null=True)
    unit_cost = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)

    objects = LineItemManager()

    @property
    def subtotal(self):
        return self.base_cost + self.unit_cost * self.quantity

    @property
    @memoized
    def applied_credit(self):
        """
        The total amount of credit applied specifically to this LineItem.
        """
        if self.creditadjustment_set.count() == 0:
            return Decimal('0.0')
        return sum([credit.amount for credit in self.creditadjustment_set.all()])

    @property
    def total(self):
        return self.subtotal + self.applied_credit

    def calculate_credit_adjustments(self):
        """
        This goes through all credit lines that:
        - specify the related feature or product rate that generated this line item
        """
        # todo: implement
        pass


class CreditLine(models.Model):
    """
    The amount of money in USD that exists can can be applied toward a specific account,
    a specific subscription, or specific rates in that subscription.
    """
    account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, null=True)
    product_rates = models.ManyToManyField(SoftwareProductRate)
    feature_rates = models.ManyToManyField(FeatureRate)
    date_created = models.DateField(auto_now_add=True)
    balance = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=4)


class CreditAdjustment(models.Model):
    """
    A record of any addition (positive amounts) s or deductions (negative amounts) that contributed to the
    current balance of the associated CreditLine.
    """
    credit_line = models.ForeignKey(CreditLine, on_delete=models.PROTECT)
    reason = models.CharField(max_length=25, default=AdjustmentReason.MANUAL, choices=AdjustmentReason.CHOICES)
    note = models.TextField()
    amount = models.DecimalField(default=Decimal('0.0'), max_digits=10, decimal_places=4)
    line_item = models.ForeignKey(LineItem, on_delete=models.PROTECT, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, null=True)
    # todo payment_method = models.ForeignKey(PaymentMethod)

    def clean(self):
        """
        Only one of either a line item or invoice may be specified as the adjuster.
        """
        if self.line_item and self.invoice is not None:
            raise ValidationError("You can't specify both an invoice and a line item.")
