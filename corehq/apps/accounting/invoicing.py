from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import calendar
import datetime

import six
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, Min, Max, Sum
from django.utils.translation import ugettext as _, ungettext

from memoized import memoized

from corehq.util.dates import get_previous_month_date_range
from corehq.apps.accounting.exceptions import (
    InvoiceAlreadyCreatedError,
    InvoiceEmailThrottledError,
    InvoiceError,
    LineItemError,
)
from corehq.apps.accounting.models import (
    LineItem, FeatureType, Invoice, CustomerInvoice, DefaultProductPlan, Subscriber,
    Subscription, BillingAccount, SubscriptionAdjustment,
    SubscriptionAdjustmentMethod, BillingRecord, CustomerBillingRecord,
    CreditLine,
    EntryPoint, WireInvoice, WireBillingRecord,
    SMALL_INVOICE_THRESHOLD, UNLIMITED_FEATURE_USAGE,
    SubscriptionType, InvoicingPlan, DomainUserHistory, SoftwarePlanEdition
)
from corehq.apps.accounting.utils import (
    ensure_domain_instance,
    log_accounting_error,
    log_accounting_info,
    months_from_date
)
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CommCareUser

DEFAULT_DAYS_UNTIL_DUE = 30


class DomainInvoiceFactory(object):
    """
    This handles all the little details when generating an Invoice.
    """

    def __init__(self, date_start, date_end, domain, recipients=None):
        """
        The Invoice generated will always be for the month preceding the
        invoicing_date.
        For example, if today is July 5, 2014 then the invoice will be from
        June 1, 2014 to June 30, 2014.
        """
        self.date_start = date_start
        self.date_end = date_end
        self.domain = ensure_domain_instance(domain)
        self.recipients = recipients
        self.logged_throttle_error = False
        if self.domain is None:
            raise InvoiceError("Domain '%s' is not a valid domain on HQ!" % domain)

    def create_invoices(self):
        subscriptions = self._get_subscriptions()
        self._ensure_full_coverage(subscriptions)
        for subscription in subscriptions:
            try:
                if subscription.account.is_customer_billing_account:
                    log_accounting_info("Skipping invoice for subscription: %s, because it is part of a Customer "
                                        "Billing Account." % (subscription))
                elif should_create_invoice(subscription, self.domain, self.date_start, self.date_end):
                    self._create_invoice_for_subscription(subscription)
            except InvoiceAlreadyCreatedError as e:
                log_accounting_error(
                    "Invoice already existed for domain %s: %s" % (self.domain.name, e),
                    show_stack_trace=True,
                )

    def _get_subscriptions(self):
        subscriptions = Subscription.visible_objects.filter(
            Q(date_end=None) | (
                Q(date_end__gt=self.date_start)
                & Q(date_end__gt=F('date_start'))
            ),
            subscriber=self.subscriber,
            date_start__lte=self.date_end
        ).order_by('date_start', 'date_end').all()
        return list(subscriptions)

    @transaction.atomic
    def _ensure_full_coverage(self, subscriptions):
        plan_version = DefaultProductPlan.get_default_plan_version()
        if not plan_version.feature_charges_exist_for_domain(self.domain):
            return

        community_ranges = self._get_community_ranges(subscriptions)
        if not community_ranges:
            return

        # First check to make sure none of the existing subscriptions is set
        # to do not invoice. Let's be on the safe side and not send a
        # community invoice out, if that's the case.
        do_not_invoice = any([s.do_not_invoice for s in subscriptions])

        account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name,
            created_by=self.__class__.__name__,
            entry_point=EntryPoint.SELF_STARTED,
        )[0]
        if account.date_confirmed_extra_charges is None:
            log_accounting_info(
                "Did not generate invoice because date_confirmed_extra_charges "
                "was null for domain %s" % self.domain.name
            )
            do_not_invoice = True

        for start_date, end_date in community_ranges:
            # create a new community subscription for each
            # date range that the domain did not have a subscription
            community_subscription = Subscription(
                account=account,
                plan_version=plan_version,
                subscriber=self.subscriber,
                date_start=start_date,
                date_end=end_date,
                do_not_invoice=do_not_invoice,
            )
            community_subscription.save()
            subscriptions.append(community_subscription)

    def _create_invoice_for_subscription(self, subscription):
        def _get_invoice_start(sub, date_start):
            return max(sub.date_start, date_start)

        def _get_invoice_end(sub, date_end):
            if sub.date_end is not None and sub.date_end <= date_end:
                # Since the Subscription is actually terminated on date_end
                # have the invoice period be until the day before date_end.
                return sub.date_end - datetime.timedelta(days=1)
            else:
                return date_end

        invoice_start = _get_invoice_start(subscription, self.date_start)
        invoice_end = _get_invoice_end(subscription, self.date_end)

        with transaction.atomic():
            invoice = self._generate_invoice(subscription, invoice_start, invoice_end)
            record = BillingRecord.generate_record(invoice)
        if record.should_send_email:
            try:
                if invoice.subscription.service_type == SubscriptionType.IMPLEMENTATION:
                    if self.recipients:
                        for email in self.recipients:
                            record.send_email(contact_email=email)
                    elif invoice.account.dimagi_contact:
                        record.send_email(contact_email=invoice.account.dimagi_contact,
                                          cc_emails=[settings.ACCOUNTS_EMAIL])
                    else:
                        record.send_email(contact_email=settings.ACCOUNTS_EMAIL)
                else:
                    for email in self.recipients or invoice.contact_emails:
                        record.send_email(contact_email=email)
            except InvoiceEmailThrottledError as e:
                if not self.logged_throttle_error:
                    log_accounting_error(six.text_type(e))
                    self.logged_throttle_error = True
        else:
            record.skipped_email = True
            record.save()

        return invoice

    def _get_community_ranges(self, subscriptions):
        community_ranges = []
        if len(subscriptions) == 0:
            return [(self.date_start, self.date_end + datetime.timedelta(days=1))]
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

                if (
                    ind == len(subscriptions) - 1 and
                    sub.date_end is not None and
                    sub.date_end <= self.date_end
                ):
                    # the last subscription ended BEFORE the end of
                    # the invoicing period
                    community_ranges.append(
                        (sub.date_end, self.date_end + datetime.timedelta(days=1))
                    )
            return community_ranges

    def _generate_invoice(self, subscription, invoice_start, invoice_end):
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

        generate_line_items(invoice, subscription)
        invoice.calculate_credit_adjustments()
        invoice.update_balance()
        invoice.save()
        visible_domain_invoices = Invoice.objects.filter(
            is_hidden=False,
            subscription__subscriber__domain=invoice.get_domain(),
        )
        total_balance = sum(invoice.balance for invoice in visible_domain_invoices)

        should_set_date_due = (
            total_balance > SMALL_INVOICE_THRESHOLD or
            (invoice.account.auto_pay_enabled and total_balance > Decimal(0))
        )
        if should_set_date_due:
            days_until_due = DEFAULT_DAYS_UNTIL_DUE
            invoice.date_due = self.date_end + datetime.timedelta(days_until_due)
        invoice.save()

        return invoice

    @property
    def subscriber(self):
        return Subscriber.objects.get_or_create(domain=self.domain.name)[0]


class DomainWireInvoiceFactory(object):

    def __init__(self, domain, date_start=None, date_end=None, contact_emails=None, account=None):
        self.date_start = date_start
        self.date_end = date_end
        self.contact_emails = contact_emails
        self.domain = ensure_domain_instance(domain)
        self.logged_throttle_error = False
        if self.domain is None:
            raise InvoiceError("Domain '{}' is not a valid domain on HQ!".format(self.domain))
        self.account = account

    @transaction.atomic
    def create_wire_invoice(self, balance):

        # Gather relevant invoices
        if self.account and self.account.is_customer_billing_account:
            invoices = CustomerInvoice.objects.filter(account=self.account)
        else:
            invoices = Invoice.objects.filter(
                subscription__subscriber__domain=self.domain.name,
                is_hidden=False,
                date_paid__exact=None
            ).order_by('-date_start')
            self.account = BillingAccount.get_or_create_account_by_domain(
                self.domain.name,
                created_by=self.__class__.__name__,
                entry_point=EntryPoint.SELF_STARTED
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

        wire_invoice = WireInvoice.objects.create(
            domain=self.domain.name,
            date_start=date_start,
            date_end=date_end,
            date_due=date_due,
            balance=balance,
        )

        record = WireBillingRecord.generate_record(wire_invoice)

        if record.should_send_email:
            try:
                for email in self.contact_emails:
                    record.send_email(contact_email=email)
            except InvoiceEmailThrottledError as e:
                # Currently wire invoices are never throttled
                if not self.logged_throttle_error:
                    log_accounting_error(six.text_type(e))
                    self.logged_throttle_error = True
        else:
            record.skipped_email = True
            record.save()

        return wire_invoice

    def create_wire_credits_invoice(self, items, amount):
        from corehq.apps.accounting.tasks import create_wire_credits_invoice
        create_wire_credits_invoice.delay(
            domain_name=self.domain.name,
            amount=amount,
            invoice_items=items,
            contact_emails=self.contact_emails
        )


class CustomerAccountInvoiceFactory(object):
    """
        This generates an invoice for a Customer Billing Account.
    """
    def __init__(self, date_start, date_end, account, recipients=None):
        """
        The Invoice generated will always be for the month preceding the
        invoicing_date.
        For example, if today is July 5, 2014 then the invoice will be from
        June 1, 2014 to June 30, 2014.
        """
        self.date_start = date_start
        self.date_end = date_end
        self.account = account
        self.recipients = recipients
        self.customer_invoice = None
        self.subscriptions = defaultdict(list)

    def create_invoice(self):
        for sub in self.account.subscription_set.filter(do_not_invoice=False):
            if not sub.plan_version.plan.edition == SoftwarePlanEdition.COMMUNITY \
                    and should_create_invoice(sub, sub.subscriber.domain, self.date_start, self.date_end):
                self.subscriptions[sub.plan_version].append(sub)
        if not self.subscriptions:
            return
        try:
            self._generate_customer_invoice()
            self._email_invoice()
        except InvoiceAlreadyCreatedError as e:
            log_accounting_error(
                "Invoice already existed for account %s: %s" % (self.account.name, e),
                show_stack_trace=True,
            )

    def _generate_customer_invoice(self):
        invoice, is_new_invoice = CustomerInvoice.objects.get_or_create(
            account=self.account,
            date_start=self.date_start,
            date_end=self.date_end
        )
        if not is_new_invoice:
            raise InvoiceAlreadyCreatedError("invoice id: {id}".format(id=invoice.id))

        all_subscriptions = []
        for plan in self.subscriptions:
            # Use oldest subscription to bill client for the full length of their software plan
            self.subscriptions[plan].sort(key=lambda s: s.date_start)
            oldest_subscription = self.subscriptions[plan][0]
            generate_line_items(invoice, oldest_subscription)
            all_subscriptions.extend(self.subscriptions[plan])
        invoice.subscriptions.set(all_subscriptions)
        invoice.calculate_credit_adjustments()
        invoice.update_balance()
        invoice.save()
        self._update_invoice_due_date(invoice, self.date_end)
        self.customer_invoice = invoice

    def _update_invoice_due_date(self, invoice, factory_date_end):
        should_set_date_due = (
            invoice.balance > SMALL_INVOICE_THRESHOLD or
            (invoice.account.auto_pay_enabled and invoice.balance > Decimal(0))
        )
        if should_set_date_due:
            invoice.date_due = factory_date_end + datetime.timedelta(DEFAULT_DAYS_UNTIL_DUE)
        invoice.save()

    def _email_invoice(self):
        record = CustomerBillingRecord.generate_record(self.customer_invoice)
        try:
            if self.recipients:
                for email in self.recipients:
                    record.send_email(contact_email=email)
            elif self.account.enterprise_admin_emails:
                for email in self.account.enterprise_admin_emails:
                    record.send_email(contact_email=email)
            elif self.account.dimagi_contact:
                record.send_email(contact_email=self.account.dimagi_contact,
                                  cc_emails=[settings.ACCOUNTS_EMAIL])
            else:
                record.send_email(contact_email=settings.ACCOUNTS_EMAIL)
        except InvoiceEmailThrottledError as e:
            log_accounting_error(str(e))


def should_create_invoice(subscription, domain, invoice_start, invoice_end):
    if subscription.is_trial:
        log_accounting_info("Skipping invoicing for Subscription %s because it's a trial." % subscription.pk)
        return False
    if subscription.skip_invoicing_if_no_feature_charges and not \
            subscription.plan_version.feature_charges_exist_for_domain(domain):
        log_accounting_info(
            "Skipping invoicing for Subscription %s because there are no feature charges."
            % subscription.pk
        )
        return False
    if subscription.date_start > invoice_end:
        # No invoice gets created if the subscription didn't start in the previous month.
        return False
    if subscription.date_end and subscription.date_end <= invoice_start:
        # No invoice gets created if the subscription ended before the invoicing period.
        return False
    return True


def generate_line_items(invoice, subscription):
    product_rate = subscription.plan_version.product_rate
    product_factory = ProductLineItemFactory(subscription, product_rate, invoice)
    product_factory.create()

    for feature_rate in subscription.plan_version.feature_rates.all():
        feature_factory_class = FeatureLineItemFactory.get_factory_by_feature_type(
            feature_rate.feature.feature_type
        )
        feature_factory = feature_factory_class(subscription, feature_rate, invoice)
        feature_factory.create()


class LineItemFactory(object):
    """
    This generates a line item based on what type of Feature or Product rate triggers it.
    """

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
        if self.subscription.subscriber.domain is None:
            raise LineItemError("No domain could be obtained as the subscriber.")
        if self.subscription.account.is_customer_billing_account:
            return [sub.subscriber.domain for sub in
                    self.subscription.account.subscription_set
                        .filter(plan_version=self.subscription.plan_version)]
        return [self.subscription.subscriber.domain]

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

    @property
    @memoized
    def is_prorated(self):
        return not (
            self.invoice.date_end.day == self._days_in_billing_period
            and self.invoice.date_start.day == 1
        )

    @property
    def num_prorated_days(self):
        return self.invoice.date_end.day - self.invoice.date_start.day + 1

    @property
    def _days_in_billing_period(self):
        return calendar.monthrange(self.invoice.date_end.year, self.invoice.date_end.month)[1]


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
    def base_description(self):
        if not self.is_prorated:
            return _("One month of %(plan_name)s Software Plan.") % {
                'plan_name': self.plan_name,
            }

    @property
    def unit_description(self):
        if self.is_prorated:
            return ungettext(
                "%(num_days)s day of %(plan_name)s Software Plan.",
                "%(num_days)s days of %(plan_name)s Software Plan.",
                self.num_prorated_days
            ) % {
                'num_days': self.num_prorated_days,
                'plan_name': self.plan_name,
            }

    @property
    def unit_cost(self):
        if self.is_prorated:
            return Decimal("%.2f" % round(self.rate.monthly_fee / self._days_in_billing_period, 2))
        return Decimal('0.0')

    @property
    def quantity(self):
        if self.is_prorated:
            return self.num_prorated_days
        if self.invoice.is_customer_invoice:
            if self.invoice.account.invoicing_plan == InvoicingPlan.QUARTERLY:
                return self.months_product_active_over_period(3)
            elif self.invoice.account.invoicing_plan == InvoicingPlan.YEARLY:
                return self.months_product_active_over_period(12)
        return 1

    def months_product_active_over_period(self, num_months):
        # Calculate the number of months out of num_months the subscription was active
        quantity = 0
        date_start = months_from_date(self.invoice.date_end, -(num_months - 1))
        while date_start < self.invoice.date_end:
            if self.subscription.date_end and self.subscription.date_end <= date_start:
                continue
            elif self.subscription.date_start <= date_start:
                quantity += 1
            date_start = date_start + relativedelta(months=1)
        return quantity

    @property
    def plan_name(self):
        return self.subscription.plan_version.plan.name

    def _auto_generate_credits(self, line_item):
        CreditLine.add_credit(
            line_item.subtotal,
            subscription=self.subscription,
            is_product=True,
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
    def unit_cost(self):
        non_prorated_unit_cost = super(UserLineItemFactory, self).unit_cost
        # To ensure that integer division is avoided
        assert isinstance(non_prorated_unit_cost, Decimal)

        if self.is_prorated:
            return Decimal(
                "%.2f" % round(
                    non_prorated_unit_cost * self.num_prorated_days / self._days_in_billing_period, 2
                )
            )
        return non_prorated_unit_cost

    @property
    def quantity(self):
        if self.invoice.is_customer_invoice and self.invoice.account.invoicing_plan != InvoicingPlan.MONTHLY:
            return self.num_excess_users_over_period
        return self.num_excess_users

    @property
    def num_excess_users_over_period(self):
        # Iterate through all months in the invoice date range to aggregate total users into one line item
        dates = self.all_month_ends_in_invoice()
        excess_users = 0
        for date in dates:
            total_users = 0
            for domain in self.subscribed_domains:
                try:
                    history = DomainUserHistory.objects.get(domain=domain, record_date=date)
                    total_users += history.num_users
                except DomainUserHistory.DoesNotExist:
                    total_users += 0
            excess_users += max(total_users - self.rate.monthly_limit, 0)
        return excess_users

    def all_month_ends_in_invoice(self):
        month_end = self.invoice.date_end
        dates = []
        while month_end > self.invoice.date_start:
            dates.append(month_end)
            _, month_end = get_previous_month_date_range(month_end)
        return dates

    @property
    def num_excess_users(self):
        if self.rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
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
        non_monthly_invoice = self.invoice.is_customer_invoice and \
            self.invoice.account.invoicing_plan != InvoicingPlan.MONTHLY
        if self.num_excess_users > 0 or (non_monthly_invoice and self.num_excess_users_over_period > 0):
            return ungettext(
                "Per User fee exceeding monthly limit of %(monthly_limit)s user.",
                "Per User fee exceeding monthly limit of %(monthly_limit)s users.",
                self.rate.monthly_limit
            ) % {
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
            sms_count += billable.multipart_count
            if sms_count <= self.rate.monthly_limit:
                # don't count fees until the free monthly limit is exceeded
                continue
            else:
                total_message_charge = billable.gateway_charge + billable.usage_charge
                num_parts_over_limit = sms_count - self.rate.monthly_limit
                already_over_limit = num_parts_over_limit >= billable.multipart_count
                if already_over_limit:
                    total_excess += total_message_charge
                else:
                    total_excess += total_message_charge * num_parts_over_limit / billable.multipart_count
        return Decimal("%.2f" % round(total_excess, 2))

    @property
    @memoized
    def quantity(self):
        return 1

    @property
    @memoized
    def unit_description(self):
        if self.rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
            return ungettext(
                "%(num_sms)d SMS Message",
                "%(num_sms)d SMS Messages",
                self.num_sms
            ) % {
                'num_sms': self.num_sms,
            }
        elif self.is_within_monthly_limit:
            return _(
                "%(num_sms)d of %(monthly_limit)d included SMS messages"
            ) % {
                'num_sms': self.num_sms,
                'monthly_limit': self.rate.monthly_limit,
            }
        else:
            assert self.rate.monthly_limit != UNLIMITED_FEATURE_USAGE
            assert self.rate.monthly_limit < self.num_sms
            num_extra = self.num_sms - self.rate.monthly_limit
            assert num_extra > 0
            return ungettext(
                "%(num_extra_sms)d SMS Message beyond %(monthly_limit)d messages included.",
                "%(num_extra_sms)d SMS Messages beyond %(monthly_limit)d messages included.",
                num_extra
            ) % {
                'num_extra_sms': num_extra,
                'monthly_limit': self.rate.monthly_limit,
            }

    @property
    @memoized
    def sms_billables_queryset(self):
        return SmsBillable.objects.filter(
            domain__in=self.subscribed_domains,
            is_valid=True,
            date_sent__gte=self.invoice.date_start,
            date_sent__lt=self.invoice.date_end + datetime.timedelta(days=1),
        ).order_by('-date_sent')

    @property
    @memoized
    def sms_billables(self):
        return list(self.sms_billables_queryset)

    @property
    @memoized
    def num_sms(self):
        return self.sms_billables_queryset.aggregate(Sum('multipart_count'))['multipart_count__sum'] or 0

    @property
    @memoized
    def is_within_monthly_limit(self):
        if self.rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
            return True
        else:
            return self.num_sms <= self.rate.monthly_limit
