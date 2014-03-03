import calendar
from decimal import Decimal
import datetime
import os
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

from reportlab.lib.units import inch
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


LOGO_FILENAME = 'corehq/apps/accounting/static/accounting/media/Dimagi-Logo-RGB.jpg'


def prepend_newline_if_not_empty(string):
    if len(string) > 0:
        return "\n" + string
    else:
        return string


class Address(object):
    def __init__(self, first_line='', second_line='', city='', region='',
                 postal_code='', country='', phone_number='',
                 email_address='', website=''):
        self.first_line = first_line
        self.second_line = second_line
        self.city = city
        self.region = region
        self.postal_code = postal_code
        self.country = country
        self.phone_number = phone_number
        self.email_address = email_address
        self.website = website

    def __str__(self):
        return '''%(first_line)s%(second_line)s
        %(city)s, %(region)s %(postal_code)s
        %(country)s%(phone_number)s%(email_address)s%(website)s
        ''' % {
            'first_line': self.first_line,
            'second_line': prepend_newline_if_not_empty(self.second_line),
            'city': self.city,
            'region': self.region,
            'postal_code': self.postal_code,
            'country': self.country,
            'phone_number': prepend_newline_if_not_empty(self.phone_number),
            'email_address': prepend_newline_if_not_empty(self.email_address),
            'website': prepend_newline_if_not_empty(self.website),
        }


LIGHT_GRAY = (0.7, 0.7, 0.7)
BLACK = (0, 0, 0)
DEFAULT_FONT_SIZE = 12


def midpoint(x1, x2):
    return (x1 + x2) * 0.5


class InvoiceTemplate(object):
    def __init__(self, filename, logo_filename=LOGO_FILENAME,
                 from_address=None, to_address=None, project_name='',
                 invoice_date=datetime.date.today(), invoice_number='',
                 terms='',
                 due_date=datetime.date.today()+datetime.timedelta(days=10)):
        self.canvas = Canvas(filename)
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)
        self.logo_filename = os.path.join(os.getcwd(), logo_filename)
        self.from_address = from_address
        self.to_address = to_address
        self.project_name = project_name
        self.invoice_date = invoice_date
        self.invoice_number = invoice_number
        self.terms = terms
        self.due_date = due_date

    def get_pdf(self):
        self.draw_logo()
        self.draw_from_address()
        self.draw_to_address()
        self.draw_project_name()
        self.draw_invoice_label()
        self.draw_details()

        self.canvas.showPage()
        self.canvas.save()

    def draw_logo(self):
        self.canvas.drawImage(self.logo_filename, inch * 0.5, inch * 2.5,
                              width=inch * 1.5, preserveAspectRatio=True)

    def draw_text(self, string, x, y):
        text = self.canvas.beginText()
        text.setTextOrigin(x, y)
        text.textLines(string)
        self.canvas.drawText(text)

    def draw_from_address(self):
        if self.from_address is not None:
            self.draw_text(str(self.from_address), inch * 3, inch * 11)

    def draw_to_address(self):
        origin_x = inch * 1
        origin_y = inch * 9.2
        self.canvas.translate(origin_x, origin_y)

        left = inch * 0
        right = inch * 4.5
        top = inch * 0.3
        middle_horizational = inch * 0
        bottom = inch * -1.7
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, middle_horizational, right - left,
                         top - middle_horizational, fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.draw_text("Bill To", left + inch * 0.2,
                       middle_horizational + inch * 0.1)

        if self.to_address is not None:
            self.draw_text(str(self.to_address), inch * 0.1, inch * -0.2)

        self.canvas.translate(-origin_x, -origin_y)

    def draw_project_name(self):
        origin_x = inch * 1
        origin_y = inch * 7
        self.canvas.translate(origin_x, origin_y)

        left = inch * 0
        middle_vertical = inch * 1
        right = inch * 4.5
        top = inch * 0
        bottom = inch * -0.3
        self.canvas.rect(left, bottom, right - left, top - bottom)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, bottom, middle_vertical - left, top - bottom,
                         fill=1)

        self.canvas.setFillColorRGB(*BLACK)
        self.canvas.drawCentredString(midpoint(left, middle_vertical),
                                      bottom + inch * 0.1,
                                      "Project")
        self.canvas.drawString(middle_vertical + inch * 0.2,
                               bottom + inch * 0.1, self.project_name)

        self.canvas.translate(-origin_x, -origin_y)

    def draw_invoice_label(self):
        self.canvas.setFontSize(size=24)
        self.canvas.drawString(inch * 6.5, inch * 10.8, "Invoice")
        self.canvas.setFontSize(DEFAULT_FONT_SIZE)

    def draw_details(self):
        origin_x = inch * 5.75
        origin_y = inch * 9.5
        self.canvas.translate(origin_x, origin_y)

        left = inch * 0
        right = inch * 2
        bottom = inch * 0
        top = inch * 1.25
        label_height = (top - bottom) / 6.0
        label_offset = label_height * 0.8
        content_offset = 1.5 * label_offset
        middle_x = midpoint(left, right)
        middle_y = midpoint(bottom, top)

        self.canvas.setFillColorRGB(*LIGHT_GRAY)
        self.canvas.rect(left, middle_y - label_height,
                         right - left, label_height, fill=1)
        self.canvas.rect(left, top - label_height, right - left, label_height,
                         fill=1)
        self.canvas.setFillColorRGB(*BLACK)

        self.canvas.rect(left, bottom, right - left, top - bottom)
        self.canvas.rect(left, bottom, 0.5 * (right - left), top - bottom)
        self.canvas.rect(left, bottom, right - left, 0.5 * (top - bottom))

        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      top - label_offset, "Date")
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      top - label_height - content_offset,
                                      str(self.invoice_date))

        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      top - label_offset, "Invoice #")
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      top - label_height - content_offset,
                                      self.invoice_number)

        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      middle_y - label_offset, "Terms")
        self.canvas.drawCentredString(midpoint(left, middle_x),
                                      middle_y - label_height - content_offset,
                                      self.terms)

        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      middle_y - label_offset, "Due Date")
        self.canvas.drawCentredString(midpoint(middle_x, right),
                                      middle_y - label_height - content_offset,
                                      str(self.due_date))

        self.canvas.translate(-origin_x, -origin_y)
