import calendar
import datetime
from collections import defaultdict
from decimal import Decimal

import simplejson
from django.conf import settings
from django.db import transaction
from django.db.models import F, Max, Min, Q, Sum
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from dateutil.relativedelta import relativedelta
from memoized import memoized

from corehq.apps.accounting.exceptions import (
    InvoiceAlreadyCreatedError,
    InvoiceEmailThrottledError,
    InvoiceError,
    LineItemError,
)
from corehq.apps.accounting.models import (
    SMALL_INVOICE_THRESHOLD,
    UNLIMITED_FEATURE_USAGE,
    BillingAccount,
    BillingRecord,
    BillingAccountWebUserHistory,
    CreditLine,
    CustomerBillingRecord,
    CustomerInvoice,
    DefaultProductPlan,
    DomainUserHistory,
    EntryPoint,
    FeatureType,
    Invoice,
    InvoicingPlan,
    LineItem,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
    WireBillingRecord,
    WireInvoice,
)
from corehq.apps.accounting.utils import (
    ensure_domain_instance,
    log_accounting_error,
    log_accounting_info,
    months_from_date,
)
from corehq.apps.domain.dbaccessors import domain_exists, deleted_domain_exists
from corehq.apps.domain.utils import get_serializable_wire_invoice_general_credit
from corehq.apps.smsbillables.models import SmsBillable
from corehq.util.dates import (
    get_first_last_days,
    get_previous_month_date_range,
)

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
            date_start__lte=self.date_end,
        ).exclude(
            plan_version__plan__edition=SoftwarePlanEdition.PAUSED,
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
                    for email in self.recipients or invoice.get_contact_emails():
                        record.send_email(contact_email=email)
            except InvoiceEmailThrottledError as e:
                if not self.logged_throttle_error:
                    log_accounting_error(str(e))
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
                    ind == len(subscriptions) - 1
                    and sub.date_end is not None
                    and sub.date_end <= self.date_end
                ):
                    # the last subscription ended BEFORE the end of
                    # the invoicing period
                    community_ranges.append(
                        (sub.date_end, self.date_end + datetime.timedelta(days=1))
                    )
            return community_ranges

    def _generate_invoice(self, subscription, invoice_start, invoice_end):
        # use create_or_get when is_hidden_to_ops is False to utilize unique index on Invoice
        # so our test will make sure the unique index prevent race condition
        # use get_or_create when is_hidden_to_ops is True
        # because our index is partial index cannot prevent duplicates in this case.
        # Note that there is a race condition in get_or_create that can result in
        # duplicate invoices.
        if subscription.do_not_invoice:
            invoice, is_new_invoice = Invoice.objects.get_or_create(
                subscription=subscription,
                date_start=invoice_start,
                date_end=invoice_end,
                is_hidden=subscription.do_not_invoice,
            )
        else:
            invoice, is_new_invoice = Invoice.objects.create_or_get(
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
            total_balance > SMALL_INVOICE_THRESHOLD
            or (invoice.account.auto_pay_enabled and total_balance > Decimal(0))
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
                    log_accounting_error(str(e))
                    self.logged_throttle_error = True
        else:
            record.skipped_email = True
            record.save()

        return wire_invoice

    def create_wire_credits_invoice(self, amount, general_credit):

        serializable_amount = simplejson.dumps(amount, use_decimal=True)
        serializable_items = get_serializable_wire_invoice_general_credit(general_credit)

        from corehq.apps.accounting.tasks import create_wire_credits_invoice
        create_wire_credits_invoice.delay(
            domain_name=self.domain.name,
            amount=serializable_amount,
            invoice_items=serializable_items,
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
            if (not sub.plan_version.plan.edition == SoftwarePlanEdition.COMMUNITY
                    and should_create_invoice(sub, sub.subscriber.domain, self.date_start, self.date_end)):
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
        # We have unique index on account, date_start and date_end
        invoice, is_new_invoice = CustomerInvoice.objects.create_or_get(
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
            invoice.balance > SMALL_INVOICE_THRESHOLD
            or (invoice.account.auto_pay_enabled and invoice.balance > Decimal(0))
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
    if subscription.plan_version.plan.edition == SoftwarePlanEdition.PAUSED:
        return False
    if not domain_exists(domain) and deleted_domain_exists(domain):
        # domain has been deleted, ignore
        return False
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
        if feature_factory_class == WebUserLineItemFactory and not subscription.account.bill_web_user:
            continue
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
        if self.subscription.account.is_customer_billing_account:
            return list(self.subscription.account.subscription_set.filter(
                Q(date_end__isnull=True) | Q(date_end__gt=self.invoice.date_start),
                date_start__lte=self.invoice.date_end
            ).filter(
                plan_version=self.subscription.plan_version
            ).values_list(
                'subscriber__domain', flat=True
            ))
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
                FeatureType.WEB_USER: WebUserLineItemFactory,
            }[feature_type]
        except KeyError:
            raise LineItemError("No line item factory exists for the feature type '%s" % feature_type)

    @property
    @memoized
    def _subscription_ends_before_invoice(self):
        return (
            self.subscription.date_end
            and self.subscription.date_end < self.invoice.date_end
        )

    @property
    @memoized
    def _subscription_starts_after_invoice(self):
        return (
            self.subscription.date_start > self.invoice.date_start
        )

    @property
    @memoized
    def subscription_date_range(self):
        if self._subscription_ends_before_invoice or self._subscription_starts_after_invoice:
            date_start = (
                self.subscription.date_start
                if self._subscription_starts_after_invoice
                else self.invoice.date_start
            )
            date_end = (
                self.subscription.date_end - datetime.timedelta(days=1)
                if self._subscription_ends_before_invoice
                else self.invoice.date_end
            )
            return "{} - {}".format(
                date_start.strftime("%b %-d"),
                date_end.strftime("%b %-d")
            )

    @property
    def _is_partial_invoice(self):
        return not (
            self.invoice.date_end.day == self._days_in_billing_period
            and self.invoice.date_start.day == 1
        )

    @property
    @memoized
    def is_prorated(self):
        return (
            self._subscription_ends_before_invoice
            or self._subscription_starts_after_invoice
            or self._is_partial_invoice
        )

    @property
    def num_prorated_days(self):
        day_start = self.invoice.date_start.day
        day_end = self.invoice.date_end.day

        if self._subscription_starts_after_invoice:
            day_start = self.subscription.date_start.day

        if self._subscription_ends_before_invoice:
            day_end = self.subscription.date_end.day - 1

        return day_end - day_start + 1

    @property
    def _days_in_billing_period(self):
        return calendar.monthrange(self.invoice.date_end.year, self.invoice.date_end.month)[1]


class ProductLineItemFactory(LineItemFactory):

    def create(self):
        line_item = super().create()
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
            return ngettext(
                "{num_days} day of {plan_name} Software Plan."
                "{subscription_date_range}",
                "{num_days} days of {plan_name} Software Plan."
                "{subscription_date_range}",
                self.num_prorated_days
            ).format(
                num_days=self.num_prorated_days,
                plan_name=self.plan_name,
                subscription_date_range=(
                    " ({})".format(self.subscription_date_range)
                    if self.subscription_date_range else ""
                ),
            )

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
    @memoized
    def quantity(self):
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
                    if not deleted_domain_exists(domain):
                        # this checks to see if the domain still exists
                        # before raising an error. If it was deleted the
                        # loop will continue
                        raise
            excess_users += max(total_users - self.rate.monthly_limit, 0)
        return excess_users

    def all_month_ends_in_invoice(self):
        _, month_end = get_first_last_days(self.invoice.date_end.year, self.invoice.date_end.month)
        dates = []
        while month_end > self.invoice.date_start:
            dates.append(month_end)
            _, month_end = get_previous_month_date_range(month_end)
        return dates

    def _unit_description_by_user_type(self, user_type):
        prorated_notice = ""
        if self.is_prorated:
            prorated_notice = _(" (Prorated for {date_range})").format(
                date_range=(
                    self.subscription_date_range
                    if self.subscription_date_range else ""
                )
            )
        if self.quantity > 0:
            return ngettext(
                "Per-{user} fee exceeding limit of {monthly_limit} {user} "
                "with plan above.{prorated_notice}",
                "Per-{user} fee exceeding limit of {monthly_limit} {user}s "
                "with plan above.{prorated_notice}",
                self.rate.monthly_limit
            ).format(
                monthly_limit=self.rate.monthly_limit,
                prorated_notice=prorated_notice,
                user=user_type
            )

    @property
    def unit_description(self):
        return self._unit_description_by_user_type("mobile user")


class WebUserLineItemFactory(UserLineItemFactory):

    @property
    @memoized
    def quantity(self):
        # Iterate through all months in the invoice date range to aggregate total users into one line item
        dates = self.all_month_ends_in_invoice()
        excess_users = 0
        for date in dates:
            total_users = 0
            try:
                history = BillingAccountWebUserHistory.objects.get(
                    billing_account=self.subscription.account, record_date=date)
                total_users += history.num_users
            except BillingAccountWebUserHistory.DoesNotExist:
                raise
            excess_users += max(total_users - self.rate.monthly_limit, 0)
        return excess_users

    @property
    def unit_description(self):
        return super()._unit_description_by_user_type("web user")


class SmsLineItemFactory(FeatureLineItemFactory):

    @property
    @memoized
    def _start_date_count_sms(self):
        """If there are multiple subscriptions in this invoice, only count the
        sms billables that occur AFTER this date for this line item.
        Otherwise, excess billables will be counted counted twice in both
        subscription timeframes.
        """
        return (
            self.subscription.date_start if self._subscription_starts_after_invoice
            else None
        )

    @property
    @memoized
    def _end_date_count_sms(self):
        """If there are multiple subscriptions in this invoice, only count the
        sms billables that occur BEFORE this date for this line item.
        Otherwise, excess billables will be counted counted twice in both
        subscription timeframes.
        """
        return (
            self.subscription.date_end if self._subscription_ends_before_invoice
            else None
        )

    @property
    @memoized
    def unit_cost(self):
        """Return aggregate cost of all the excess SMS"""
        total_excess = Decimal('0.0')
        if self.is_within_monthly_limit:
            return total_excess

        sms_count = 0
        for billable in self.sms_billables:
            sms_count += billable.multipart_count
            if sms_count <= self.rate.monthly_limit:
                # don't count fees until the free monthly limit is exceeded
                continue
            elif self._start_date_count_sms and (
                billable.date_sent.date() < self._start_date_count_sms
            ):
                # count the SMS billables sent before the start date toward
                # the monthly total & limit for the line item, but don't include
                # the usage charge in the total_excess for this line item
                # (otherwise it will be counted twice)
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
            return ngettext(
                "{num_sms} SMS Message",
                "{num_sms} SMS Messages",
                self.num_sms
            ).format(
                num_sms=self.num_sms,
            )
        elif self.is_within_monthly_limit:
            return _(
                "{num_sms} of {monthly_limit} included SMS{date_range}."
            ).format(
                num_sms=self.num_sms,
                monthly_limit=self.rate.monthly_limit,
                date_range=(
                    _(" from {}").format(self.subscription_date_range)
                    if self.subscription_date_range else ""
                )
            )
        else:
            assert self.rate.monthly_limit != UNLIMITED_FEATURE_USAGE
            assert self.rate.monthly_limit < self.num_sms
            num_extra = self.num_sms - self.rate.monthly_limit
            assert num_extra > 0
            return ngettext(
                "{num_extra_sms} SMS message beyond {monthly_limit} "
                "messages included{date_range}.",
                "{num_extra_sms} SMS messages beyond {monthly_limit} "
                "messages included{date_range}.",
                num_extra
            ).format(
                num_extra_sms=num_extra,
                monthly_limit=self.rate.monthly_limit,
                date_range=(
                    _(" from {}").format(self.subscription_date_range)
                    if self.subscription_date_range else ""
                )
            )

    @property
    @memoized
    def sms_billables_queryset(self):
        return SmsBillable.objects.filter(
            domain__in=self.subscribed_domains,
            is_valid=True,
            date_sent__gte=self.invoice.date_start,

            # Don't count any SMS billables towards the monthly total &
            # limit if they were sent AFTER the end date of the current
            # subscription related to this line item. Save it for the
            # next subscription in the invoice.
            date_sent__lt=(
                self._end_date_count_sms if self._end_date_count_sms
                else self.invoice.date_end + datetime.timedelta(days=1)
            ),

        ).order_by('date_sent')

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
