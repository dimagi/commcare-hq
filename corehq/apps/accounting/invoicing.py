import calendar
from decimal import Decimal
import datetime
from django.db.models import ProtectedError

from django.utils.translation import ugettext as _
from corehq.apps.accounting.utils import assure_domain_instance
from dimagi.utils.decorators.memoized import memoized

from corehq import Domain
from corehq.apps.accounting.exceptions import LineItemError, InvoiceError
from corehq.apps.accounting.models import (LineItem, FeatureType, Invoice, DefaultProductPlan, Subscriber,
                                           Subscription, BillingAccount, SubscriptionAdjustment,
                                           SubscriptionAdjustmentMethod)
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CommCareUser

from reportlab.pdfgen.canvas import Canvas

DEFAULT_DAYS_UNTIL_DUE = 10


class InvoiceFactory(object):
    """
    This handles all the little details when generating an Invoice.
    """
    subscription = None

    def __init__(self, date_start, date_end):
        """
        The Invoice generated will always be for the month preceding the invoicing_date.
        For example, if today is July 5, 2014 then the invoice will be from
        June 1, 2014 to June 30, 2014
        """
        self.date_start = date_start
        self.date_end = date_end

    def create(self):
        if self.subscription is None:
            raise InvoiceError("Cannot create an invoice without a subscription.")

        days_until_due = DEFAULT_DAYS_UNTIL_DUE
        if self.subscription.date_delay_invoicing is not None:
            td = self.subscription.date_delay_invoicing - self.date_end
            days_until_due = max(days_until_due, td.days)
        date_due = self.date_end + datetime.timedelta(days_until_due)

        invoice = Invoice(
            subscription=self.subscription,
            date_start=self.date_start,
            date_end=self.date_end,
            date_due=date_due,
        )
        invoice.save()
        self.generate_line_items(invoice)
        invoice.update_balance()
        if invoice.balance == Decimal('0.0'):
            invoice.lineitem_set.all().delete()
            invoice.delete()
            return None

        invoice.calculate_credit_adjustments()
        invoice.update_balance()
        # generate PDF
        invoice.save()
        return invoice

    def generate_line_items(self, invoice):
        for product_rate in self.subscription.plan_version.product_rates.all():
            product_factory = ProductLineItemFactory(self.subscription, product_rate, invoice)
            product_factory.create()

        for feature_rate in self.subscription.plan_version.feature_rates.all():
            feature_factory_class = FeatureLineItemFactory.get_factory_by_feature_type(
                feature_rate.feature.feature_type
            )
            feature_factory = feature_factory_class(self.subscription, feature_rate, invoice)
            feature_factory.create()


class SubscriptionInvoiceFactory(InvoiceFactory):

    def __init__(self, date_start, date_end, subscription):
        super(SubscriptionInvoiceFactory, self).__init__(date_start, date_end)
        self.subscription = subscription
        self.date_start = self.subscription.date_start if self.subscription.date_start > date_start else date_start
        self.date_end = self.subscription.date_end if self.subscription.date_end < date_end else date_end


class CommunityInvoiceFactory(InvoiceFactory):

    def __init__(self, date_start, date_end, domain):
        super(CommunityInvoiceFactory, self).__init__(date_start, date_end)
        self.domain = assure_domain_instance(domain)

    @property
    @memoized
    def account(self):
        """
        First try to grab the account used for the last subscription.
        If an account is not found, create it.
        """
        account, _ = BillingAccount.get_or_create_account_by_domain(self.domain.name, self.__class__.__name__)
        return account

    @property
    def software_plan_version(self):
        return DefaultProductPlan.get_default_plan_by_domain(self.domain)

    @property
    @memoized
    def subscription(self):
        """
        If we're arriving here, it's because there wasn't a subscription for the period of this invoice,
        so let's create one.
        """
        subscriber, _ = Subscriber.objects.get_or_create(domain=self.domain.name)
        subscription = Subscription(
            account=self.account,
            subscriber=subscriber,
            plan_version=self.software_plan_version,
            date_start=self.date_start,
            date_end=self.date_end,
        )
        subscription.save()
        return subscription

    def create(self):
        invoice = super(CommunityInvoiceFactory, self).create()
        if invoice is None:
            # no charges were created, so delete the temporary subscription to the community plan for this
            # invoicing period
            self.subscription.delete()
            try:
                # delete the account too (is only successful if no other subscriptions reference it)
                self.account.delete()
            except ProtectedError:
                pass
        else:
            SubscriptionAdjustment.record_adjustment(
                self.subscription,
                method=SubscriptionAdjustmentMethod.TASK,
                invoice=invoice,
            )
        return invoice


class LineItemFactory(object):
    """
    This generates a line item based on what type of Feature or Product rate triggers it.
    """
    line_item_details_template = ""  # todo

    def __init__(self, subscription, rate, invoice):
        self.subscription = subscription
        self.rate = rate
        self.invoice = invoice

    @property
    def unit_description(self):
        """
        If this returns None then the unit unit_description, unit_cost, and quantity
        will not show up for the line item in the printed invoice.
        """
        return None

    @property
    def base_description(self):
        """
        If this returns None then the unit base_description and base_cost
        will not show up for the line item in the printed invoice.
        """
        return None

    @property
    def unit_cost(self):
        raise NotImplementedError()

    @property
    def quantity(self):
        raise NotImplementedError()

    @property
    @memoized
    def subscribed_domains(self):
        if self.subscription.subscriber.organization is None and self.subscription.subscriber.domain is None:
            raise LineItemError("No domain or organization could be obtained as the subscriber.")
        if self.subscription.subscriber.organization is not None:
            return Domain.get_by_organization(self.subscription.subscriber.organization)
        return [self.subscription.subscriber.domain]

    @property
    @memoized
    def line_item_details(self):
        return []

    def create(self):
        line_item = LineItem(
            invoice=self.invoice,
            base_description=self.base_description,
            unit_description=self.unit_description,
            unit_cost=self.unit_cost,
            quantity=self.quantity,
        )
        return line_item

    @classmethod
    def get_factory_by_feature_type(cls, feature_type):
        try:
            return {
                FeatureType.SMS: SmsLineItemFactory,
                FeatureType.USER: UserLineItemFactory,
            }[feature_type]
        except KeyError:
            raise LineItemError("No line item factory exists for the feature type '%s" % feature_type)


class ProductLineItemFactory(LineItemFactory):

    def create(self):
        line_item = super(ProductLineItemFactory, self).create()
        line_item.product_rate = self.rate
        if not self.is_prorated:
            line_item.base_cost = self.rate.monthly_fee
        line_item.save()
        return line_item

    @property
    @memoized
    def is_prorated(self):
        last_day = calendar.monthrange(self.invoice.date_end.year, self.invoice.date_end.month)[1]
        return not (self.invoice.date_end.day == last_day and self.invoice.date_start.day == 1)

    @property
    def base_description(self):
        if not self.is_prorated:
            return _("One month of %(plan_name)s Software Plan." % {
                'plan_name': self.rate.product.name,
            })

    @property
    def unit_description(self):
        if self.is_prorated:
            return _("%(num_days)s day%(pluralize)s of %(plan_name)s Software Plan." % {
                'num_days': self.num_prorated_days,
                'pluralize': "" if self.num_prorated_days == 1 else "s",
                'plan_name': self.rate.product.name,
            })

    @property
    def num_prorated_days(self):
        return self.invoice.date_end.day - self.invoice.date_start.day + 1

    @property
    def unit_cost(self):
        if self.is_prorated:
            return Decimal("%.2f" % round(self.rate.monthly_fee / 30, 2))
        return Decimal('0.0')

    @property
    def quantity(self):
        if self.is_prorated:
            return self.num_prorated_days
        return 1


class FeatureLineItemFactory(LineItemFactory):

    def create(self):
        line_item = super(FeatureLineItemFactory, self).create()
        line_item.feature_rate = self.rate
        line_item.save()
        return line_item

    @property
    def unit_cost(self):
        return self.rate.per_excess_fee


class UserLineItemFactory(FeatureLineItemFactory):

    @property
    def quantity(self):
        return self.num_excess_users

    @property
    def num_excess_users(self):
        return max(self.num_users - self.rate.monthly_limit, 0)

    @property
    @memoized
    def num_users(self):
        total_users = 0
        for domain in self.subscribed_domains:
            total_users += CommCareUser.total_by_domain(domain, is_active=True)
        return total_users

    @property
    def unit_description(self):
        if self.num_excess_users > 0:
            return _("Per User fee exceeding monthly limit of %(monthly_limit)s users." % {
                'monthly_limit': self.rate.monthly_limit,
            })


class SmsLineItemFactory(FeatureLineItemFactory):

    @property
    @memoized
    def unit_cost(self):
        total_excess = Decimal('0.0')
        if self.is_within_monthly_limit:
            return total_excess

        sms_count = 0
        for billable in self.sms_billables:
            sms_count += 1
            if sms_count <= self.rate.monthly_limit:
                # don't count fees until the free monthly limit is exceeded
                continue
            if billable.usage_fee:
                total_excess += billable.usage_fee.amount
            if billable.gateway_fee:
                total_excess += billable.gateway_fee.amount * billable.gateway_fee_conversion_rate
        return Decimal("%.2f" % round(total_excess, 2))

    @property
    @memoized
    def quantity(self):
        return 1

    @property
    @memoized
    def unit_description(self):
        if self.is_within_monthly_limit:
            return _("%(num_sms)d of %(monthly_limit)d included SMS messages") % {
                'num_sms': self.num_sms,
                'monthly_limit': self.rate.monthly_limit,
            }
        if self.rate.monthly_limit == 0:
            return _("%(num_sms)d SMS Message(plural)s" % {
                'num_sms': self.num_sms,
                'plural': '' if self.num_sms == 1 else 's',
            })
        num_extra = self.rate.monthly_limit - self.num_sms
        return _("%(num_extra_sms)d SMS Message%(plural)s beyond %(monthly_limit)d messages included." % {
            'num_extra_sms': num_extra,
            'plural': '' if num_extra == 0 else 's',
            'monthly_limit': self.rate.monthly_limit,
        })

    @property
    @memoized
    def sms_billables_queryset(self):
        return SmsBillable.objects.filter(
            domain__in=self.subscribed_domains,
            is_valid=True,
            date_sent__range=[self.invoice.date_start, self.invoice.date_end]
        ).order_by('-date_sent')

    @property
    @memoized
    def sms_billables(self):
        return list(self.sms_billables_queryset)

    @property
    @memoized
    def num_sms(self):
        return self.sms_billables_queryset.count()

    @property
    @memoized
    def is_within_monthly_limit(self):
        return self.num_sms - self.rate.monthly_limit <= 0

    @property
    def line_item_details(self):
        details = []
        for billable in self.sms_billables:
            gateway_api = billable.gateway_fee.criteria.backend_api_id if billable.gateway_fee else "custom"
            gateway_fee = billable.gateway_fee.amount if billable.gateway_fee else Decimal('0.0')
            usage_fee = billable.usage_fee.amount if billable.usage_fee else Decimal('0.0')
            total_fee = gateway_fee + usage_fee
            details.append(
                [billable.phone_number, billable.direction, gateway_api, total_fee]
            )
        return details


class InvoiceTemplate(object):

    def __init__(self, filename):
        self.filename = filename

    def get_pdf(self):
        self.canvas = Canvas(self.filename)

        self.canvas.showPage()
        self.canvas.save()
