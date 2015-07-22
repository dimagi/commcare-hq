import calendar
from decimal import Decimal
import datetime
import logging
from django.db.models import F, Q, Min, Max
from django.template.loader import render_to_string

from django.utils.translation import ugettext as _
from corehq.apps.accounting.utils import ensure_domain_instance
from dimagi.utils.decorators.memoized import memoized

from corehq import Domain
from corehq.apps.accounting.exceptions import (
    LineItemError,
    InvoiceError,
    InvoiceEmailThrottledError,
    BillingContactInfoError,
    InvoiceAlreadyCreatedError,
)
from corehq.apps.accounting.models import (
    LineItem, FeatureType, Invoice, DefaultProductPlan, Subscriber,
    Subscription, BillingAccount, SubscriptionAdjustment,
    SubscriptionAdjustmentMethod, BillingRecord,
    BillingContactInfo, SoftwarePlanEdition, CreditLine,
    EntryPoint, WireInvoice, WireBillingRecord,
    SMALL_INVOICE_THRESHOLD, WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
)
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CommCareUser

logger = logging.getLogger('accounting')


DEFAULT_DAYS_UNTIL_DUE = 30


class DomainInvoiceFactory(object):
    """
    This handles all the little details when generating an Invoice.
    """

    def __init__(self, date_start, date_end, domain):
        """
        The Invoice generated will always be for the month preceding the
        invoicing_date.
        For example, if today is July 5, 2014 then the invoice will be from
        June 1, 2014 to June 30, 2014.
        """
        self.date_start = date_start
        self.date_end = date_end
        self.domain = ensure_domain_instance(domain)
        self.logged_throttle_error = False
        if self.domain is None:
            raise InvoiceError("Domain '%s' is not a valid domain on HQ!"
                               % domain)
        self.is_community_invoice = False

    @property
    def subscriber(self):
        return Subscriber.objects.get_or_create(domain=self.domain.name)[0]

    def get_subscriptions(self):
        subscriptions = Subscription.objects.filter(
            subscriber=self.subscriber, date_start__lte=self.date_end
        ).filter(Q(date_end=None) | Q(date_end__gt=self.date_start)
        ).filter(Q(date_end=None) | Q(date_end__gt=F('date_start'))
        ).order_by('date_start', 'date_end').all()
        return list(subscriptions)

    def get_community_ranges(self, subscriptions):
        community_ranges = []
        if len(subscriptions) == 0:
            community_ranges.append((self.date_start, self.date_end))
        else:
            prev_sub_end = self.date_end
            for ind, sub in enumerate(subscriptions):
                if ind == 0 and sub.date_start > self.date_start:
                    # the first subscription started AFTER the beginning
                    # of the invoicing period
                    community_ranges.append((self.date_start, sub.date_start))

                if prev_sub_end < self.date_end and sub.date_start > prev_sub_end:
                    community_ranges.append((prev_sub_end, sub.date_start))
                prev_sub_end = sub.date_end

                if (ind == len(subscriptions) - 1
                    and sub.date_end is not None
                    and sub.date_end <= self.date_end
                ):
                    # the last subscription ended BEFORE the end of
                    # the invoicing period
                    community_ranges.append(
                        (sub.date_end, self.date_end + datetime.timedelta(days=1))
                    )
        return community_ranges

    def ensure_full_coverage(self, subscriptions):
        plan_version = DefaultProductPlan.get_default_plan_by_domain(
            self.domain, edition=SoftwarePlanEdition.COMMUNITY
        ).plan.get_version()
        if not plan_version.feature_charges_exist_for_domain(self.domain):
            return
        community_ranges = self.get_community_ranges(subscriptions)
        if not community_ranges:
            return
        do_not_invoice = any([s.do_not_invoice for s in subscriptions])
        account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name,
            created_by=self.__class__.__name__,
            created_by_invoicing=True,
            entry_point=EntryPoint.SELF_STARTED,
        )[0]
        if account.date_confirmed_extra_charges is None:
            logger.info(
                "Did not generate invoice because date_confirmed_extra_charges "
                "was null for domain %s" % self.domain.name
            )
            do_not_invoice = True
        if not BillingContactInfo.objects.filter(account=account).exists():
            # No contact information exists for this account.
            # This shouldn't happen, but if it does, we can't continue
            # with the invoice generation.
            raise BillingContactInfoError(
                "Project %s has incurred charges, but does not have their "
                "Billing Contact Info filled out." % self.domain.name
            )
        # First check to make sure none of the existing subscriptions is set
        # to do not invoice. Let's be on the safe side and not send a
        # community invoice out, if that's the case.
        for c in community_ranges:
            # create a new community subscription for each
            # date range that the domain did not have a subscription
            community_subscription = Subscription(
                account=account,
                plan_version=plan_version,
                subscriber=self.subscriber,
                date_start=c[0],
                date_end=c[1],
                do_not_invoice=do_not_invoice,
            )
            community_subscription.save()
            subscriptions.append(community_subscription)

    def create_invoices(self):
        subscriptions = self.get_subscriptions()
        self.ensure_full_coverage(subscriptions)
        for subscription in subscriptions:
            self.create_invoice_for_subscription(subscription)

    def create_invoice_for_subscription(self, subscription):
        if subscription.is_trial:
            # Don't create invoices for trial subscriptions
            logger.info("[BILLING] Skipping invoicing for Subscription "
                        "%s because it's a trial." % subscription.pk)
            return

        if subscription.date_start > self.date_start:
            invoice_start = subscription.date_start
        else:
            invoice_start = self.date_start

        if (subscription.date_end is not None
           and subscription.date_end <= self.date_end):
            # Since the Subscription is actually terminated on date_end
            # have the invoice period be until the day before date_end.
            invoice_end = subscription.date_end - datetime.timedelta(days=1)
        else:
            invoice_end = self.date_end

        invoice, is_new_invoice = Invoice.objects.get_or_create(
            subscription=subscription,
            date_start=invoice_start,
            date_end=invoice_end,
            is_hidden=subscription.do_not_invoice,
        )

        if not is_new_invoice:
            raise InvoiceAlreadyCreatedError("invoice id: {id}".format(id=invoice.id))

        if subscription.subscriptionadjustment_set.count() == 0:
            # record that the subscription was created
            SubscriptionAdjustment.record_adjustment(
                subscription,
                method=SubscriptionAdjustmentMethod.TASK,
                invoice=invoice,
            )

        self.generate_line_items(invoice, subscription)
        invoice.calculate_credit_adjustments()
        invoice.update_balance()
        invoice.save()
        total_balance = sum(invoice.balance for invoice in Invoice.objects.filter(
            is_hidden=False,
            subscription__subscriber__domain=invoice.get_domain(),
        ))
        if total_balance > SMALL_INVOICE_THRESHOLD:
            days_until_due = DEFAULT_DAYS_UNTIL_DUE
            if subscription.date_delay_invoicing is not None:
                td = subscription.date_delay_invoicing - self.date_end
                days_until_due = max(days_until_due, td.days)
            invoice.date_due = self.date_end + datetime.timedelta(days_until_due)
        invoice.save()

        record = BillingRecord.generate_record(invoice)
        try:
            record.send_email()
        except InvoiceEmailThrottledError as e:
            if not self.logged_throttle_error:
                logger.error("[BILLING] %s" % e)
                self.logged_throttle_error = True

        return invoice

    def generate_line_items(self, invoice, subscription):
        for product_rate in subscription.plan_version.product_rates.all():
            product_factory = ProductLineItemFactory(subscription, product_rate, invoice)
            product_factory.create()

        for feature_rate in subscription.plan_version.feature_rates.all():
            feature_factory_class = FeatureLineItemFactory.get_factory_by_feature_type(
                feature_rate.feature.feature_type
            )
            feature_factory = feature_factory_class(subscription, feature_rate, invoice)
            feature_factory.create()


class DomainWireInvoiceFactory(object):

    def __init__(self, domain, date_start=None, date_end=None, contact_emails=None):
        self.date_start = date_start
        self.date_end = date_end
        self.contact_emails = contact_emails
        self.domain = ensure_domain_instance(domain)
        self.logged_throttle_error = False
        if self.domain is None:
            raise InvoiceError("Domain '{}' is not a valid domain on HQ!".format(self.domain))

    def create_wire_invoice(self, balance):

        # Gather relevant invoices
        invoices = Invoice.objects.filter(
            subscription__subscriber__domain=self.domain,
            is_hidden=False,
            date_paid__exact=None,
        ).order_by('-date_start')

        account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name,
            created_by=self.__class__.__name__,
            created_by_invoicing=True,
            entry_point=EntryPoint.SELF_STARTED,
        )[0]

        # If no start date supplied, default earliest start date of unpaid invoices
        if self.date_start:
            date_start = self.date_start
        else:
            date_start = invoices.aggregate(Min('date_start'))['date_start__min']

        # If no end date supplied, default latest end date of unpaid invoices
        if self.date_end:
            date_end = self.date_end
        else:
            date_end = invoices.aggregate(Max('date_end'))['date_end__max']

        if not date_end:
            date_end = datetime.datetime.today()

        date_due = date_end + datetime.timedelta(DEFAULT_DAYS_UNTIL_DUE)

        # TODO: figure out how to handle line items
        wire_invoice = WireInvoice.objects.create(
            domain=self.domain.name,
            date_start=date_start,
            date_end=date_end,
            date_due=date_due,
            balance=balance,
            account=account
        )

        record = WireBillingRecord.generate_record(wire_invoice)

        try:
            record.send_email(contact_emails=self.contact_emails)
        except InvoiceEmailThrottledError as e:
            # Currently wire invoices are never throttled
            if not self.logged_throttle_error:
                logger.error("[BILLING] %s" % e)
                self.logged_throttle_error = True

        return wire_invoice

    def create_wire_credits_invoice(self, items, amount):
        from corehq.apps.accounting.tasks import create_wire_credits_invoice
        create_wire_credits_invoice.delay(
            domain_name=self.domain.name,
            account_created_by=self.__class__.__name__,
            account_entry_point=EntryPoint.SELF_STARTED,
            amount=amount,
            invoice_items=items,
            contact_emails=self.contact_emails
        )


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

        if self.subscription.auto_generate_credits:
            self._auto_generate_credits(line_item)

        return line_item

    @property
    @memoized
    def is_prorated(self):
        last_day = calendar.monthrange(self.invoice.date_end.year, self.invoice.date_end.month)[1]
        return not (self.invoice.date_end.day == last_day and self.invoice.date_start.day == 1)

    @property
    def base_description(self):
        if not self.is_prorated:
            return _("One month of %(plan_name)s Software Plan.") % {
                'plan_name': self.plan_name,
            }

    @property
    def unit_description(self):
        if self.is_prorated:
            return _("%(num_days)s day%(pluralize)s of %(plan_name)s Software Plan.") % {
                'num_days': self.num_prorated_days,
                'pluralize': "" if self.num_prorated_days == 1 else "s",
                'plan_name': self.plan_name,
            }

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

    @property
    def plan_name(self):
        return self.subscription.plan_version.plan.name

    def _auto_generate_credits(self, line_item):
        CreditLine.add_credit(
            line_item.subtotal,
            subscription=self.subscription,
            product_type=self.rate.product.product_type,
            permit_inactive=True,
        )


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
        if self.rate.monthly_limit == -1:
            return 0
        else:
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
            return _("Per User fee exceeding monthly limit of "
                     "%(monthly_limit)s users.") % {
                         'monthly_limit': self.rate.monthly_limit,
                     }


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
                total_excess += billable.gateway_charge
        return Decimal("%.2f" % round(total_excess, 2))

    @property
    @memoized
    def quantity(self):
        return 1

    @property
    @memoized
    def unit_description(self):
        if self.rate.monthly_limit == -1:
            return _("%(num_sms)d SMS Message%(plural)s") % {
                'num_sms': self.num_sms,
                'plural': '' if self.num_sms == 1 else 's',
            }
        elif self.is_within_monthly_limit:
            return _(
                "%(num_sms)d of %(monthly_limit)d included SMS messages"
            ) % {
                'num_sms': self.num_sms,
                'monthly_limit': self.rate.monthly_limit,
            }
        else:
            assert self.rate.monthly_limit != -1
            assert self.rate.monthly_limit < self.num_sms
            num_extra = self.num_sms - self.rate.monthly_limit
            assert num_extra > 0
            return _(
                "%(num_extra_sms)d SMS %(messages)s beyond "
                "%(monthly_limit)d messages included."
            ) % {
                'num_extra_sms': num_extra,
                'messages': (_('Messages') if num_extra == 1
                             else _('Messages')),
                'monthly_limit': self.rate.monthly_limit,
            }

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
        if self.rate.monthly_limit == -1:
            return True
        else:
            return self.num_sms <= self.rate.monthly_limit

    @property
    def line_item_details(self):
        details = []
        for billable in self.sms_billables:
            gateway_api = billable.gateway_fee.criteria.backend_api_id if billable.gateway_fee else "custom"
            gateway_fee = billable.gateway_charge
            usage_fee = billable.usage_fee.amount if billable.usage_fee else Decimal('0.0')
            total_fee = gateway_fee + usage_fee
            details.append(
                [billable.phone_number, billable.direction, gateway_api, total_fee]
            )
        return details
