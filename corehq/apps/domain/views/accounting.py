import datetime
import json
from collections import namedtuple
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Sum
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseForbidden,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import View

import dateutil
from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq.apps.accounting.decorators import always_allow_project_access
from corehq.apps.accounting.utils.downgrade import can_domain_unpause
from dimagi.utils.web import json_response

from corehq import privileges
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.exceptions import (
    NewSubscriptionError,
    PaymentRequestError,
    SubscriptionAdjustmentError,
    SubscriptionRenewalError,
)
from corehq.apps.accounting.forms import (
    AnnualPlanContactForm,
    EnterprisePlanContactForm,
)
from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.accounting.models import (
    MINIMUM_SUBSCRIPTION_LENGTH,
    UNLIMITED_FEATURE_USAGE,
    BillingAccount,
    BillingAccountType,
    BillingRecord,
    CreditLine,
    CustomerInvoice,
    DefaultProductPlan,
    EntryPoint,
    Invoice,
    InvoicePdf,
    LastPayment,
    PaymentMethodType,
    SoftwarePlanEdition,
    StripePaymentMethod,
    Subscription,
    SubscriptionType,
    WireInvoice,
)
from corehq.apps.accounting.payment_handlers import (
    BulkStripePaymentHandler,
    CreditStripePaymentHandler,
    InvoiceStripePaymentHandler,
)
from corehq.apps.accounting.subscription_changes import (
    DomainDowngradeStatusHandler,
)
from corehq.apps.accounting.usage import FeatureUsageCalculator
from corehq.apps.accounting.user_text import (
    DESC_BY_EDITION,
    get_feature_name,
    get_feature_recurring_interval,
)
from corehq.apps.accounting.utils import (
    fmt_dollar_amount,
    get_change_status,
    is_downgrade,
    log_accounting_error,
    quantize_accounting_decimal,
    get_paused_plan_context,
    pause_current_subscription,
)
from corehq.apps.accounting.utils.stripe import get_customer_cards
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    require_superuser,
    LoginAndDomainMixin,
)
from corehq.apps.domain.forms import (
    INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS,
    AdvancedExtendedTrialForm,
    ConfirmNewSubscriptionForm,
    ConfirmSubscriptionRenewalForm,
    ContractedPartnerForm,
    DimagiOnlyEnterpriseForm,
    EditBillingAccountInfoForm,
    SelectSubscriptionTypeForm,
)
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.domain.views.settings import (
    BaseAdminProjectSettingsView,
    BaseProjectSettingsView,
)
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import use_jquery_ui
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.hqwebapp.views import BasePageView, CRUDPaginatedViewMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.const import USER_DATE_FORMAT

PAYMENT_ERROR_MESSAGES = {
    400: gettext_lazy('Your request was not formatted properly.'),
    403: gettext_lazy('Forbidden.'),
    404: gettext_lazy('Page not found.'),
    500: gettext_lazy("There was an error processing your request."
           " We're working quickly to fix the issue. Please try again shortly."),
}


class SubscriptionUpgradeRequiredView(LoginAndDomainMixin, BasePageView, DomainViewMixin):
    page_title = gettext_lazy("Upgrade Required")
    template_name = "domain/insufficient_privilege_notification.html"

    @property
    def page_url(self):
        return self.request.get_full_path

    @property
    def page_name(self):
        return _("Sorry, you do not have access to %(feature_name)s") % {
            'feature_name': self.feature_name,
        }

    @property
    def is_domain_admin(self):
        if not hasattr(self.request, 'couch_user'):
            return False
        return self.request.couch_user.is_domain_admin(self.domain)

    @property
    def page_context(self):
        context = {
            'domain': self.domain,
            'feature_name': self.feature_name,
            'plan_name': self.required_plan_name,
            'change_subscription_url': reverse(SelectPlanView.urlname,
                                               args=[self.domain]),
            'is_domain_admin': self.is_domain_admin,
        }
        context.update(get_paused_plan_context(self.request, self.domain))
        return context

    @property
    def missing_privilege(self):
        return self.args[1]

    @property
    def feature_name(self):
        return privileges.Titles.get_name_from_privilege(self.missing_privilege)

    @property
    def required_plan_name(self):
        return DefaultProductPlan.get_lowest_edition([self.missing_privilege])

    def get(self, request, *args, **kwargs):
        self.request = request
        self.args = args
        return super(SubscriptionUpgradeRequiredView, self).get(
            request, *args, **kwargs
        )


class DomainAccountingSettings(BaseProjectSettingsView):

    @method_decorator(always_allow_project_access)
    @method_decorator(require_permission(HqPermissions.edit_billing))
    def dispatch(self, request, *args, **kwargs):
        return super(DomainAccountingSettings, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    @property
    def current_subscription(self):
        return Subscription.get_active_subscription_by_domain(self.domain)

    @property
    def main_context(self):
        context = super(DomainAccountingSettings, self).main_context
        context['show_prepaid_modal'] = False
        return context


class DomainSubscriptionView(DomainAccountingSettings):
    urlname = 'domain_subscription_view'
    template_name = 'domain/current_subscription.html'
    page_title = gettext_lazy("Current Subscription")

    @property
    def can_purchase_credits(self):
        return self.request.couch_user.can_edit_billing()

    @property
    @memoized
    def plan(self):
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()
        date_end = None
        next_subscription = {
            'exists': False,
            'can_renew': False,
            'name': None,
            'price': None,
        }
        cards = None
        trial_length = None
        if subscription:
            cards = get_customer_cards(self.request.user.username)
            date_end = (subscription.date_end.strftime(USER_DATE_FORMAT)
                        if subscription.date_end is not None else "--")

            if subscription.date_end is not None:
                if subscription.is_renewed:
                    next_subscription.update({
                        'exists': True,
                        'is_paused': subscription.next_subscription.plan_version.is_paused,
                        'date_start': subscription.next_subscription.date_start.strftime(USER_DATE_FORMAT),
                        'name': subscription.next_subscription.plan_version.plan.name,
                        'price': (
                            _("USD %s /month")
                            % subscription.next_subscription.plan_version.product_rate.monthly_fee
                        ),
                    })

                else:
                    days_left = (subscription.date_end - datetime.date.today()).days
                    next_subscription.update({
                        'can_renew': days_left <= 30,
                        'renew_url': reverse(SubscriptionRenewalView.urlname, args=[self.domain]),
                    })

            if subscription.is_trial and subscription.date_end is not None:
                trial_length = (subscription.date_end - subscription.date_start).days

        if subscription:
            credit_lines = CreditLine.get_non_general_credits_by_subscription(subscription)
            credit_lines = [cl for cl in credit_lines if cl.balance > 0]
            has_credits_in_non_general_credit_line = len(credit_lines) > 0
        else:
            has_credits_in_non_general_credit_line = False

        info = {
            'products': [self.get_product_summary(plan_version, self.account, subscription)],
            'features': self.get_feature_summary(plan_version, self.account, subscription),
            'general_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_by_subscription_and_features(
                    subscription
                ) if subscription else None
            )),
            'account_general_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_for_account(
                    self.account
                ) if self.account else None
            )),
            'css_class': "label-plan label-plan-%s" % plan_version.plan.edition.lower(),
            'do_not_invoice': subscription.do_not_invoice if subscription is not None else False,
            'is_trial': subscription.is_trial if subscription is not None else False,
            'trial_length': trial_length,
            'date_start': (subscription.date_start.strftime(USER_DATE_FORMAT)
                           if subscription is not None else None),
            'date_end': date_end,
            'cards': cards,
            'next_subscription': next_subscription,
            'has_credits_in_non_general_credit_line': has_credits_in_non_general_credit_line,
            'is_annual_plan': plan_version.plan.is_annual_plan,
            'is_paused': subscription.plan_version.is_paused,
            'previous_subscription_edition': (
                subscription.previous_subscription.plan_version.plan.edition
                if subscription.previous_subscription else ""
            ),
        }
        info['has_account_level_credit'] = (
            any(
                product_info['account_credit'] and product_info['account_credit']['is_visible']
                for product_info in info['products']
            )
            or info['account_general_credit'] and info['account_general_credit']['is_visible']
        )
        info.update(plan_version.user_facing_description)

        return info

    def _fmt_credit(self, credit_amount=None):
        if credit_amount is None:
            return {
                'amount': "--",
            }
        return {
            'amount': fmt_dollar_amount(credit_amount),
            'is_visible': credit_amount != Decimal('0.0'),
        }

    def _credit_grand_total(self, credit_lines):
        return sum([c.balance for c in credit_lines]) if credit_lines else Decimal('0.00')

    def get_product_summary(self, plan_version, account, subscription):
        product_rate = plan_version.product_rate
        return {
            'monthly_fee': _("USD %s /month") % product_rate.monthly_fee,
            'subscription_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_by_subscription_and_features(
                    subscription, is_product=True
                ) if subscription else None
            )),
            'account_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_for_account(
                    account, is_product=True
                ) if account else None
            )),
        }

    def get_feature_summary(self, plan_version, account, subscription):
        def _get_feature_info(feature_rate):
            usage = FeatureUsageCalculator(feature_rate, self.domain).get_usage()
            feature_type = feature_rate.feature.feature_type
            if feature_rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
                remaining = limit = _('Unlimited')
            else:
                limit = feature_rate.monthly_limit
                remaining = limit - usage
                if remaining < 0:
                    remaining = _("%d over limit") % (-1 * remaining)
            return {
                'name': get_feature_name(feature_type),
                'usage': usage,
                'limit': limit,
                'remaining': remaining,
                'type': feature_type,
                'recurring_interval': get_feature_recurring_interval(feature_type),
                'subscription_credit': self._fmt_credit(self._credit_grand_total(
                    CreditLine.get_credits_by_subscription_and_features(
                        subscription, feature_type=feature_type
                    ) if subscription else None
                )),
                'account_credit': self._fmt_credit(self._credit_grand_total(
                    CreditLine.get_credits_for_account(
                        account, feature_type=feature_type
                    ) if account else None
                )),
            }

        return list(map(_get_feature_info, plan_version.feature_rates.all()))

    @property
    def page_context(self):
        from corehq.apps.domain.views.sms import SMSRatesView
        subs = self.current_subscription
        return {
            'plan': self.plan,
            'change_plan_url': reverse(SelectPlanView.urlname, args=[self.domain]),
            'can_purchase_credits': self.can_purchase_credits,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'payment_error_messages': PAYMENT_ERROR_MESSAGES,
            'sms_rate_calc_url': reverse(SMSRatesView.urlname,
                                         args=[self.domain]),
            'user_email': self.request.couch_user.username,
            'show_account_credits': any(
                feature['account_credit'].get('is_visible')
                for feature in self.plan.get('features')
            ),
            'can_change_subscription': subs and subs.user_can_change_subscription(self.request.user),
        }


class EditExistingBillingAccountView(DomainAccountingSettings, AsyncHandlerMixin):
    template_name = 'domain/update_billing_contact_info.html'
    urlname = 'domain_update_billing_info'
    page_title = gettext_lazy("Billing Information")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    @memoized
    def billing_info_form(self):
        is_ops_user = has_privilege(self.request, privileges.ACCOUNTING_ADMIN)
        if self.request.method == 'POST':
            return EditBillingAccountInfoForm(
                self.account, self.domain, self.request.couch_user.username, data=self.request.POST,
                is_ops_user=is_ops_user
            )
        return EditBillingAccountInfoForm(self.account, self.domain, self.request.couch_user.username,
                                          is_ops_user=is_ops_user)

    def dispatch(self, request, *args, **kwargs):
        if self.account is None:
            raise Http404()
        return super(EditExistingBillingAccountView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'billing_account_info_form': self.billing_info_form,
            'cards': self._get_cards(),
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        }

    def _get_cards(self):
        if not settings.STRIPE_PRIVATE_KEY:
            return []

        user = self.request.user.username
        payment_method, new_payment_method = StripePaymentMethod.objects.get_or_create(
            web_user=user,
            method_type=PaymentMethodType.STRIPE,
        )
        return payment_method.all_cards_serialized(self.account)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.billing_info_form.is_valid():
            is_saved = self.billing_info_form.save()
            if not is_saved:
                messages.error(
                    request, _("It appears that there was an issue updating your contact information. "
                               "We've been notified of the issue. Please try submitting again, and if the problem "
                               "persists, please try in a few hours."))
            else:
                messages.success(
                    request, _("Billing contact information was successfully updated.")
                )
                return HttpResponseRedirect(reverse(EditExistingBillingAccountView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class DomainBillingStatementsView(DomainAccountingSettings, CRUDPaginatedViewMixin):
    template_name = 'domain/billing_statements.html'
    urlname = 'domain_billing_statements'
    page_title = gettext_lazy("Billing Statements")

    limit_text = gettext_lazy("statements per page")
    empty_notification = gettext_lazy("No Billing Statements match the current criteria.")
    loading_message = gettext_lazy("Loading statements...")

    @property
    def stripe_cards(self):
        return get_customer_cards(self.request.user.username)

    @property
    def show_hidden(self):
        if not self.request.user.is_superuser:
            return False
        return bool(self.request.POST.get('additionalData[show_hidden]'))

    @property
    def show_unpaid(self):
        try:
            return json.loads(self.request.POST.get('additionalData[show_unpaid]'))
        except TypeError:
            return False

    @property
    def invoices(self):
        invoices = Invoice.objects.filter(subscription__subscriber__domain=self.domain)
        if not self.show_hidden:
            invoices = invoices.filter(is_hidden=False)
        if self.show_unpaid:
            invoices = invoices.filter(date_paid__exact=None)
        return invoices.order_by('-date_start', '-date_end')

    @property
    def total(self):
        return self.paginated_invoices.count

    @property
    @memoized
    def paginated_invoices(self):
        return Paginator(self.invoices, self.limit)

    @property
    def total_balance(self):
        """
        Returns the total balance of unpaid, unhidden invoices.
        Doesn't take into account the view settings on the page.
        """
        invoices = (Invoice.objects
                    .filter(subscription__subscriber__domain=self.domain)
                    .filter(date_paid__exact=None)
                    .filter(is_hidden=False))
        return invoices.aggregate(
            total_balance=Sum('balance')
        ).get('total_balance') or 0.00

    @property
    def column_names(self):
        return [
            _("Statement No."),
            _("Plan"),
            _("Billing Period"),
            _("Date Due"),
            _("Payment Status"),
            _("PDF"),
        ]

    @property
    def page_context(self):
        pagination_context = self.pagination_context
        pagination_context.update({
            'stripe_options': {
                'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                'stripe_cards': self.stripe_cards,
            },
            'payment_error_messages': PAYMENT_ERROR_MESSAGES,
            'payment_urls': {
                'process_invoice_payment_url': reverse(
                    InvoiceStripePaymentView.urlname,
                    args=[self.domain],
                ),
                'process_bulk_payment_url': reverse(
                    BulkStripePaymentView.urlname,
                    args=[self.domain],
                ),
                'process_wire_invoice_url': reverse(
                    WireInvoiceView.urlname,
                    args=[self.domain],
                ),
            },
            'total_balance': self.total_balance,
            'show_plan': True,
            'show_overdue_invoice_modal': False,
        })
        return pagination_context

    @property
    def can_pay_invoices(self):
        return self.request.couch_user.is_domain_admin(self.domain)

    @property
    def paginated_list(self):
        for invoice in self.paginated_invoices.page(self.page).object_list:
            try:
                last_billing_record = BillingRecord.objects.filter(
                    invoice=invoice
                ).latest('date_created')
                if invoice.is_paid:
                    payment_status = _("Paid on %s.") % invoice.date_paid.strftime(USER_DATE_FORMAT)
                    payment_class = "label label-default"
                else:
                    payment_status = _("Not Paid")
                    payment_class = "label label-danger"
                date_due = (
                    (invoice.date_due.strftime(USER_DATE_FORMAT)
                     if not invoice.is_paid else _("Already Paid"))
                    if invoice.date_due else _("None")
                )
                yield {
                    'itemData': {
                        'id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'start': invoice.date_start.strftime(USER_DATE_FORMAT),
                        'end': invoice.date_end.strftime(USER_DATE_FORMAT),
                        'plan': invoice.subscription.plan_version.user_facing_description,
                        'payment_status': payment_status,
                        'payment_class': payment_class,
                        'date_due': date_due,
                        'pdfUrl': reverse(
                            BillingStatementPdfView.urlname,
                            args=[self.domain, last_billing_record.pdf_data_id]
                        ),
                        'canMakePayment': (not invoice.is_paid
                                           and self.can_pay_invoices),
                        'balance': "%s" % quantize_accounting_decimal(invoice.balance),
                    },
                    'template': 'statement-row-template',
                }
            except BillingRecord.DoesNotExist:
                log_accounting_error(
                    "An invoice was generated for %(invoice_id)d "
                    "(domain: %(domain)s), but no billing record!" % {
                        'invoice_id': invoice.id,
                        'domain': self.domain,
                    },
                    show_stack_trace=True
                )

    def refresh_item(self, item_id):
        pass

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def dispatch(self, request, *args, **kwargs):
        if self.account is None:
            raise Http404()
        return super(DomainBillingStatementsView, self).dispatch(request, *args, **kwargs)


class BaseStripePaymentView(DomainAccountingSettings):
    http_method_names = ['post']

    @property
    def account(self):
        raise NotImplementedError("you must implement the property account")

    @property
    @memoized
    def billing_admin(self):
        if self.request.couch_user.can_edit_billing():
            return self.request.couch_user.username
        else:
            raise PaymentRequestError(
                "The logged in user was not a billing admin."
            )

    def get_or_create_payment_method(self):
        return StripePaymentMethod.objects.get_or_create(
            web_user=self.billing_admin,
            method_type=PaymentMethodType.STRIPE,
        )[0]

    def get_payment_handler(self):
        """Returns a StripePaymentHandler object
        """
        raise NotImplementedError("You must implement get_payment_handler()")

    def post(self, request, *args, **kwargs):
        try:
            payment_handler = self.get_payment_handler()
            response = payment_handler.process_request(request)
        except PaymentRequestError as e:
            log_accounting_error(
                "Failed to process Stripe Payment due to bad "
                "request for domain %(domain)s user %(web_user)s: "
                "%(error)s" % {
                    'domain': self.domain,
                    'web_user': self.request.user.username,
                    'error': e,
                }
            )
            response = {
                'error': {
                    'message': _(
                        "There was an issue processing your payment. No "
                        "charges were made. We're looking into the issue "
                        "as quickly as possible. Sorry for the inconvenience."
                    )
                }
            }

        return json_response(response)


class CreditsStripePaymentView(BaseStripePaymentView):
    urlname = 'domain_credits_payment'

    @property
    @memoized
    def account(self):
        return BillingAccount.get_or_create_account_by_domain(
            self.domain,
            created_by=self.request.user.username,
            account_type=BillingAccountType.USER_CREATED,
            entry_point=EntryPoint.SELF_STARTED,
            last_payment_method=LastPayment.CC_ONE_TIME,
        )[0]

    def get_payment_handler(self):
        return CreditStripePaymentHandler(
            self.get_or_create_payment_method(),
            self.domain,
            self.account,
            subscription=Subscription.get_active_subscription_by_domain(self.domain),
            post_data=self.request.POST.copy(),
        )


class CreditsWireInvoiceView(DomainAccountingSettings):
    http_method_names = ['post']
    urlname = 'domain_wire_payment'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(CreditsWireInvoiceView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        emails = request.POST.get('emails', []).split()
        invalid_emails = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid_emails.append(email)
        if invalid_emails:
            message = _('The following e-mail addresses contain invalid characters, or are missing required '
                        'characters: ') + ', '.join(['"{}"'.format(email) for email in invalid_emails])
            return json_response({'error': {'message': message}})
        amount = Decimal(request.POST.get('amount', 0))
        if amount < 0:
            message = _('There was an error processing your request. Please try again.')
            return json_response({'error': {'message': message}})
        general_credit = Decimal(request.POST.get('general_credit', 0))
        wire_invoice_factory = DomainWireInvoiceFactory(request.domain, contact_emails=emails)
        try:
            wire_invoice_factory.create_wire_credits_invoice(amount, general_credit)
        except Exception as e:
            return json_response({'error': {'message': str(e)}})

        return json_response({'success': True})


class InvoiceStripePaymentView(BaseStripePaymentView):
    urlname = 'domain_invoice_payment'

    @property
    @memoized
    def invoice(self):
        try:
            invoice_id = self.request.POST['invoice_id']
        except IndexError:
            raise PaymentRequestError("invoice_id is required")
        try:
            if self.account and self.account.is_customer_billing_account:
                return CustomerInvoice.objects.get(pk=invoice_id)
            else:
                return Invoice.objects.get(pk=invoice_id)
        except (Invoice.DoesNotExist, CustomerInvoice.DoesNotExist):
            raise PaymentRequestError(
                "Could not find a matching invoice for invoice_id '%s'"
                % invoice_id
            )

    @property
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    def get_payment_handler(self):
        return InvoiceStripePaymentHandler(
            self.get_or_create_payment_method(), self.domain, self.invoice
        )


class BulkStripePaymentView(BaseStripePaymentView):
    urlname = 'domain_bulk_payment'

    @property
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    def get_payment_handler(self):
        return BulkStripePaymentHandler(
            self.get_or_create_payment_method(), self.domain
        )


class WireInvoiceView(View):
    http_method_names = ['post']
    urlname = 'domain_wire_invoice'

    @method_decorator(always_allow_project_access)
    @method_decorator(require_permission(HqPermissions.edit_billing))
    def dispatch(self, request, *args, **kwargs):
        return super(WireInvoiceView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        emails = request.POST.get('emails', []).split()
        balance = Decimal(request.POST.get('customPaymentAmount', 0))

        from corehq.apps.accounting.utils.account import (
            get_account_or_404,
            request_has_permissions_for_enterprise_admin,
        )
        account = get_account_or_404(request.domain)
        if (account.is_customer_billing_account
                and not request_has_permissions_for_enterprise_admin(request, account)):
            return HttpResponseForbidden()

        wire_invoice_factory = DomainWireInvoiceFactory(request.domain, contact_emails=emails, account=account)
        try:
            wire_invoice_factory.create_wire_invoice(balance)
        except Exception as e:
            return json_response({'error': {'message', e}})

        return json_response({'success': True})


class BillingStatementPdfView(View):
    urlname = 'domain_billing_statement_download'

    @method_decorator(always_allow_project_access)
    @method_decorator(require_permission(HqPermissions.edit_billing))
    def dispatch(self, request, *args, **kwargs):
        return super(BillingStatementPdfView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        domain = args[0]
        statement_id = kwargs.get('statement_id')
        if statement_id is None or domain is None:
            raise Http404()
        try:
            invoice_pdf = InvoicePdf.get(statement_id)
        except ResourceNotFound:
            raise Http404()

        try:
            if invoice_pdf.is_wire:
                invoice = WireInvoice.objects.get(
                    pk=invoice_pdf.invoice_id,
                    domain=domain
                )
            elif invoice_pdf.is_customer:
                invoice = CustomerInvoice.objects.get(
                    pk=invoice_pdf.invoice_id
                )
            else:
                invoice = Invoice.objects.get(
                    pk=invoice_pdf.invoice_id,
                    subscription__subscriber__domain=domain
                )
        except (Invoice.DoesNotExist, WireInvoice.DoesNotExist, CustomerInvoice.DoesNotExist):
            raise Http404()

        if invoice.is_customer_invoice:
            from corehq.apps.accounting.utils.account import (
                get_account_or_404,
                request_has_permissions_for_enterprise_admin,
            )
            account = get_account_or_404(request.domain)
            if not request_has_permissions_for_enterprise_admin(request, account):
                return HttpResponseForbidden()

            filename = "%(pdf_id)s_%(account)s_%(filename)s" % {
                'pdf_id': invoice_pdf._id,
                'account': account,
                'filename': invoice_pdf.get_filename(invoice)
            }
        else:
            if invoice.is_wire:
                edition = 'Bulk'
            else:
                edition = DESC_BY_EDITION[invoice.subscription.plan_version.plan.edition]['name']
            filename = "%(pdf_id)s_%(domain)s_%(edition)s_%(filename)s" % {
                'pdf_id': invoice_pdf._id,
                'domain': domain,
                'edition': edition,
                'filename': invoice_pdf.get_filename(invoice),
            }
        try:
            data = invoice_pdf.get_data(invoice)
            response = HttpResponse(data, content_type='application/pdf')
            response['Content-Disposition'] = 'inline;filename="%s' % filename
        except Exception as e:
            log_accounting_error('Fetching invoice PDF failed: %s' % e)
            return HttpResponse(_("Could not obtain billing statement. "
                                  "An issue has been submitted."))
        return response


class InternalSubscriptionManagementView(BaseAdminProjectSettingsView):
    template_name = 'domain/internal_subscription_management.html'
    urlname = 'internal_subscription_mgmt'
    page_title = gettext_lazy("Dimagi Internal Subscription Management")
    form_classes = INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS

    @method_decorator(always_allow_project_access)
    @method_decorator(require_superuser)
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(InternalSubscriptionManagementView, self).dispatch(request, *args, **kwargs)

    @method_decorator(require_superuser)
    def post(self, request, *args, **kwargs):
        form = self.get_post_form
        if form.is_valid():
            try:
                form.process_subscription_management()
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
            except (NewSubscriptionError, SubscriptionAdjustmentError) as e:
                messages.error(self.request, format_html(
                    'This request will require Ops assistance. '
                    'Please explain to <a href="mailto:{ops_email}">{ops_email}</a>'
                    ' what you\'re trying to do and report the following error: <strong>"{error}"</strong>',
                    error=str(e),
                    ops_email=settings.ACCOUNTS_EMAIL)
                )
        return self.get(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(InternalSubscriptionManagementView, self).main_context
        context['show_prepaid_modal'] = False
        return context

    @property
    def page_context(self):
        return {
            'is_form_editable': self.is_form_editable,
            'plan_name': Subscription.get_subscribed_plan_by_domain(self.domain),
            'select_subscription_type_form': self.select_subscription_type_form,
            'subscription_management_forms': list(self.slug_to_form.values()),
            'today': datetime.date.today(),
        }

    @property
    def get_post_form(self):
        return self.slug_to_form[self.request.POST.get('slug')]

    @property
    @memoized
    def slug_to_form(self):
        def create_form(form_class):
            if self.request.method == 'POST' and form_class.slug == self.request.POST.get('slug'):
                return form_class(self.domain, self.request.couch_user.username, self.request.POST)
            return form_class(self.domain, self.request.couch_user.username)
        return {form_class.slug: create_form(form_class) for form_class in self.form_classes}

    @property
    @memoized
    def select_subscription_type_form(self):
        if self.request.method == 'POST' and 'slug' in self.request.POST:
            return SelectSubscriptionTypeForm({
                'subscription_type': self.request.POST['slug'],
            })

        subscription_type = None
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if subscription is None:
            subscription_type = None
        else:
            plan = subscription.plan_version.plan
            if subscription.service_type == SubscriptionType.IMPLEMENTATION:
                subscription_type = ContractedPartnerForm.slug
            elif plan.edition == SoftwarePlanEdition.ENTERPRISE:
                subscription_type = DimagiOnlyEnterpriseForm.slug
            elif plan.edition == SoftwarePlanEdition.ADVANCED:
                subscription_type = AdvancedExtendedTrialForm.slug

        return SelectSubscriptionTypeForm(
            {'subscription_type': subscription_type},
            disable_input=not self.is_form_editable,
        )

    @property
    def is_form_editable(self):
        return not self.slug_to_form[ContractedPartnerForm.slug].is_uneditable


PlanOption = namedtuple(
    'PlanOption',
    ['name', 'monthly_price', 'annual_price', 'description']
)


class SelectPlanView(DomainAccountingSettings):
    template_name = 'domain/select_plan.html'
    urlname = 'domain_select_plan'
    page_title = gettext_lazy("Change Plan")
    step_title = gettext_lazy("Select Plan")
    edition = None
    lead_text = gettext_lazy("Please select a plan below that fits your organization's needs.")

    @property
    @memoized
    def can_domain_unpause(self):
        return can_domain_unpause(self.domain)

    @property
    def plan_options(self):
        return [
            PlanOption(
                SoftwarePlanEdition.STANDARD,
                "$300",
                "$250",
                _("For programs with one-time data collection needs, simple "
                  "case management workflows, and basic M&E requirements."),
            ),
            PlanOption(
                SoftwarePlanEdition.PRO,
                "$600",
                "$500",
                _("For programs with complex case management needs, field "
                  "staff collaborating on tasks, and M&E teams that need to "
                  "clean and report on data."),
            ),
            PlanOption(
                SoftwarePlanEdition.ADVANCED,
                "$1200",
                "$1000",
                _("For programs with distributed field staff, facility-based "
                  "workflows, and advanced security needs. Also for M&E teams "
                  "integrating data with 3rd party analytics."),
            ),
            PlanOption(
                SoftwarePlanEdition.ENTERPRISE,
                _("Contact Us"),
                _("Contact Us"),
                _("For organizations that need a sustainable path to scale "
                  "mobile data collection and service delivery across multiple "
                  "teams, programs, or countries."),
            )
        ]

    @property
    def start_date_after_minimum_subscription(self):
        if self.current_subscription is None:
            return ""
        elif self.current_subscription.is_trial:
            return ""
        else:
            new_start_date = self.current_subscription.date_start + \
                datetime.timedelta(days=MINIMUM_SUBSCRIPTION_LENGTH)
            return new_start_date.strftime(USER_DATE_FORMAT)

    @property
    def next_subscription_edition(self):
        if self.current_subscription is None:
            return None
        elif self.current_subscription.next_subscription is None:
            return None
        else:
            return self.current_subscription.next_subscription.plan_version.plan.edition

    @property
    def edition_name(self):
        if self.edition:
            return DESC_BY_EDITION[self.edition]['name']

    @property
    def parent_pages(self):
        return [
            {
                'title': DomainSubscriptionView.page_title,
                'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
            }
        ]

    @property
    def steps(self):
        edition_name = " (%s)" % self.edition_name if self.edition_name else ""
        return [
            {
                'title': _("1. Select a Plan%(edition_name)s") % {
                    "edition_name": edition_name
                },
                'url': reverse(SelectPlanView.urlname, args=[self.domain]),
            }
        ]

    @property
    def main_context(self):
        context = super(SelectPlanView, self).main_context
        context.update({
            'steps': self.steps,
            'step_title': self.step_title,
            'lead_text': self.lead_text,
        })
        return context

    @property
    def page_context(self):
        if self.current_subscription is not None and not self.current_subscription.is_trial:
            current_price = self.current_subscription.plan_version.product_rate.monthly_fee
            default_price = DefaultProductPlan.get_default_plan_version(
                edition=self.current_subscription.plan_version.plan.edition
            ).product_rate.monthly_fee
        else:
            current_price = 0
            default_price = 0
        return {
            'editions': [
                edition.lower()
                for edition in [
                    SoftwarePlanEdition.COMMUNITY,
                    SoftwarePlanEdition.STANDARD,
                    SoftwarePlanEdition.PRO,
                    SoftwarePlanEdition.ADVANCED,
                    SoftwarePlanEdition.ENTERPRISE,
                ]
            ],
            'plan_options': [p._asdict() for p in self.plan_options],
            'current_edition': (self.current_subscription.plan_version.plan.edition.lower()
                                if self.current_subscription is not None
                                and not self.current_subscription.is_trial
                                else ""),
            'current_price': "${0:.0f}".format(current_price),
            'is_price_discounted': current_price < default_price,
            'start_date_after_minimum_subscription': self.start_date_after_minimum_subscription,
            'subscription_below_minimum': (self.current_subscription.is_below_minimum_subscription
                                           if self.current_subscription is not None else False),
            'next_subscription_edition': self.next_subscription_edition,
            'can_domain_unpause': self.can_domain_unpause,
        }


class SelectedEnterprisePlanView(SelectPlanView):
    template_name = 'domain/selected_enterprise_plan.html'
    urlname = 'enterprise_request_quote'
    step_title = gettext_lazy("Contact Dimagi")
    edition = SoftwarePlanEdition.ENTERPRISE

    @property
    def steps(self):
        last_steps = super(SelectedEnterprisePlanView, self).steps
        last_steps.append({
            'title': _("2. Contact Dimagi"),
            'url': reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    @memoized
    def is_not_redirect(self):
        return 'plan_edition' not in self.request.POST

    @property
    @memoized
    def enterprise_contact_form(self):
        if self.request.method == 'POST' and self.is_not_redirect:
            return EnterprisePlanContactForm(self.domain, self.request.couch_user, data=self.request.POST)
        return EnterprisePlanContactForm(self.domain, self.request.couch_user)

    @property
    def page_context(self):
        return {
            'enterprise_contact_form': self.enterprise_contact_form,
        }

    def post(self, request, *args, **kwargs):
        if self.is_not_redirect and self.enterprise_contact_form.is_valid():
            self.enterprise_contact_form.send_message()
            messages.success(request, _("Your request was sent to Dimagi. "
                                        "We will follow up shortly."))
            return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class SelectedAnnualPlanView(SelectPlanView):
    template_name = 'domain/selected_annual_plan.html'
    urlname = 'annual_plan_request_quote'
    step_title = gettext_lazy("Contact Dimagi")

    @property
    def steps(self):
        last_steps = super(SelectedAnnualPlanView, self).steps
        last_steps.append({
            'title': _("2. Contact Dimagi"),
            'url': reverse(SelectedAnnualPlanView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    def on_annual_plan(self):
        if self.current_subscription is None:
            return False
        else:
            return self.current_subscription.plan_version.plan.is_annual_plan

    @property
    @memoized
    def is_not_redirect(self):
        return 'plan_edition' not in self.request.POST

    @property
    @memoized
    def edition(self):
        if self.on_annual_plan:
            return self.current_subscription.plan_version.plan.edition
        edition = self.request.GET.get('plan_edition').title()
        if edition not in [e[0] for e in SoftwarePlanEdition.CHOICES]:
            raise Http404()
        return edition

    @property
    @memoized
    def annual_plan_contact_form(self):
        if self.request.method == 'POST' and self.is_not_redirect:
            return AnnualPlanContactForm(self.domain, self.request.couch_user, self.on_annual_plan,
                                         data=self.request.POST)
        return AnnualPlanContactForm(self.domain, self.request.couch_user, self.on_annual_plan)

    @property
    def page_context(self):
        return {
            'annual_plan_contact_form': self.annual_plan_contact_form,
            'on_annual_plan': self.on_annual_plan,
            'edition': self.edition,
            'selected_enterprise_plan': self.edition == SoftwarePlanEdition.ENTERPRISE
        }

    def post(self, request, *args, **kwargs):
        if self.is_not_redirect and self.annual_plan_contact_form.is_valid():
            self.annual_plan_contact_form.send_message()
            messages.success(request, _("Your request was sent to Dimagi. "
                                        "We will try our best to follow up in a timely manner."))
            return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class ConfirmSelectedPlanView(SelectPlanView):
    template_name = 'domain/confirm_plan.html'
    urlname = 'confirm_selected_plan'

    @property
    def step_title(self):
        if self.is_paused:
            return _("Confirm Pause")
        return _("Confirm Subscription")

    @property
    def steps(self):
        last_steps = super(ConfirmSelectedPlanView, self).steps
        last_steps.append({
            'title': _("2. Confirm Pause") if self.is_paused else _("2. Confirm Subscription"),
            'url': reverse(SelectPlanView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    def is_paused(self):
        return self.edition == SoftwarePlanEdition.PAUSED

    @property
    @memoized
    def edition(self):
        edition = self.request.POST.get('plan_edition').title()
        if edition not in [e[0] for e in SoftwarePlanEdition.CHOICES]:
            raise Http404()
        return edition

    @property
    @memoized
    def selected_plan_version(self):
        return DefaultProductPlan.get_default_plan_version(self.edition)

    @property
    def downgrade_messages(self):
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        downgrades = get_change_status(
            subscription.plan_version if subscription else None,
            self.selected_plan_version
        )[1]
        downgrade_handler = DomainDowngradeStatusHandler(
            self.domain_object, self.selected_plan_version, downgrades,
        )
        return downgrade_handler.get_response()

    @property
    def is_upgrade(self):
        if self.current_subscription.is_trial:
            return True
        elif self.current_subscription.plan_version.plan.edition == self.edition:
            return False
        else:
            return not is_downgrade(
                current_edition=self.current_subscription.plan_version.plan.edition,
                next_edition=self.edition
            )

    @property
    def is_same_edition(self):
        return self.current_subscription.plan_version.plan.edition == self.edition

    @property
    def is_downgrade_before_minimum(self):
        if self.is_upgrade:
            return False
        elif self.current_subscription is None or self.current_subscription.is_trial:
            return False
        elif self.current_subscription.is_below_minimum_subscription:
            return True
        else:
            return False

    @property
    def current_subscription_end_date(self):
        if self.is_downgrade_before_minimum:
            return self.current_subscription.date_start + \
                datetime.timedelta(days=MINIMUM_SUBSCRIPTION_LENGTH)
        else:
            return datetime.date.today()

    @property
    def next_invoice_date(self):
        # Next invoice date is the first day of the next month
        return datetime.date.today().replace(day=1) + dateutil.relativedelta.relativedelta(months=1)

    @property
    def page_context(self):
        return {
            'downgrade_messages': self.downgrade_messages,
            'is_upgrade': self.is_upgrade,
            'is_same_edition': self.is_same_edition,
            'next_invoice_date': self.next_invoice_date.strftime(USER_DATE_FORMAT),
            'current_plan': (self.current_subscription.plan_version.plan.edition
                             if self.current_subscription is not None else None),
            'is_downgrade_before_minimum': self.is_downgrade_before_minimum,
            'current_subscription_end_date': self.current_subscription_end_date.strftime(USER_DATE_FORMAT),
            'start_date_after_minimum_subscription': self.start_date_after_minimum_subscription,
            'new_plan_edition': self.edition,
            'is_paused': self.is_paused,
            'tile_css': 'tile-{}'.format(self.edition.lower()),
        }

    @property
    def main_context(self):
        context = super(ConfirmSelectedPlanView, self).main_context
        context.update({
            'plan': (self.current_subscription.plan_version.user_facing_description if self.is_same_edition
                     else self.selected_plan_version.user_facing_description),
        })
        return context

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse(SelectPlanView.urlname, args=[self.domain]))

    def post(self, request, *args, **kwargs):
        if not self.can_domain_unpause:
            return HttpResponseRedirect(reverse(SelectPlanView.urlname, args=[self.domain]))
        if self.edition == SoftwarePlanEdition.ENTERPRISE:
            return HttpResponseRedirect(reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]))
        return super(ConfirmSelectedPlanView, self).get(request, *args, **kwargs)


class ConfirmBillingAccountInfoView(ConfirmSelectedPlanView, AsyncHandlerMixin):
    template_name = 'domain/confirm_billing_info.html'
    urlname = 'confirm_billing_account_info'
    step_title = gettext_lazy("Confirm Billing Information")
    is_new = False
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    def steps(self):
        last_steps = super(ConfirmBillingAccountInfoView, self).steps
        last_steps.append({
            'title': _("3. Confirm Billing Account"),
            'url': reverse(ConfirmBillingAccountInfoView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    @memoized
    def account(self):
        if self.current_subscription:
            return self.current_subscription.account
        account, self.is_new = BillingAccount.get_or_create_account_by_domain(
            self.domain,
            created_by=self.request.couch_user.username,
            account_type=BillingAccountType.USER_CREATED,
            entry_point=EntryPoint.SELF_STARTED,
        )
        return account

    @property
    def payment_method(self):
        user = self.request.user.username
        payment_method, __ = StripePaymentMethod.objects.get_or_create(
            web_user=user,
            method_type=PaymentMethodType.STRIPE,
        )
        return payment_method

    @property
    @memoized
    def is_form_post(self):
        return 'company_name' in self.request.POST

    @property
    def downgrade_email_note(self):
        if self.is_upgrade:
            return None
        if self.is_same_edition:
            return None
        return _get_downgrade_or_pause_note(self.request)

    @property
    @memoized
    def billing_account_info_form(self):
        if self.request.method == 'POST' and self.is_form_post:
            return ConfirmNewSubscriptionForm(
                self.account, self.domain, self.request.couch_user.username,
                self.selected_plan_version, self.current_subscription, data=self.request.POST
            )
        return ConfirmNewSubscriptionForm(self.account, self.domain, self.request.couch_user.username,
                                          self.selected_plan_version, self.current_subscription)

    @property
    def page_context(self):
        return {
            'billing_account_info_form': self.billing_account_info_form,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'cards': self.payment_method.all_cards_serialized(self.account),
            'downgrade_email_note': self.downgrade_email_note
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response

        if not self.can_domain_unpause:
            return HttpResponseRedirect(reverse(SelectPlanView.urlname, args=[self.domain]))

        if self.is_form_post and self.billing_account_info_form.is_valid():
            if not self.current_subscription.user_can_change_subscription(self.request.user):
                messages.error(
                    request, _(
                        "You do not have permission to change the subscription for this customer-level account. "
                        "Please reach out to the %s enterprise admin for help."
                    ) % self.account.name
                )
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
            if self.selected_plan_version.plan.edition not in SoftwarePlanEdition.SELF_SERVICE_ORDER:
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
            is_saved = self.billing_account_info_form.save()
            software_plan_name = DESC_BY_EDITION[self.selected_plan_version.plan.edition]['name']
            next_subscription = self.current_subscription.next_subscription

            if is_saved:
                if not request.user.is_superuser:
                    if self.billing_account_info_form.is_same_edition():
                        self.send_keep_subscription_email()
                    elif self.billing_account_info_form.is_downgrade_from_paid_plan():
                        self.send_downgrade_email()
                if self.billing_account_info_form.is_same_edition():
                    # Choosing to keep the same subscription
                    message = _(
                        "Thank you for choosing to stay with your %(software_plan_name)s "
                        "Edition Plan subscription."
                    ) % {
                        'software_plan_name': software_plan_name,
                    }
                elif next_subscription is not None:
                    # New subscription has been scheduled for the future
                    current_subscription_edition = self.current_subscription.plan_version.plan.edition
                    start_date = next_subscription.date_start.strftime(USER_DATE_FORMAT)
                    message = _(
                        "You have successfully scheduled your current %(current_subscription_edition)s "
                        "Edition Plan subscription to downgrade to the %(software_plan_name)s Edition Plan "
                        "on %(start_date)s."
                    ) % {
                        'current_subscription_edition': current_subscription_edition,
                        'software_plan_name': software_plan_name,
                        'start_date': start_date,
                    }
                else:
                    message = _(
                        "Your project has been successfully subscribed to the %s Edition Plan."
                    ) % software_plan_name
                messages.success(
                    request, message
                )
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))

            downgrade_date = next_subscription.date_start.strftime(USER_DATE_FORMAT)
            messages.error(
                request, _(
                    "You have already scheduled a downgrade to the %(software_plan_name)s Software Plan on "
                    "%(downgrade_date)s. If this is a mistake, please reach out to %(contact_email)."
                ) % {
                    'software_plan_name': software_plan_name,
                    'downgrade_date': downgrade_date,
                    'contact_email': settings.INVOICING_CONTACT_EMAIL,
                }
            )

        return super(ConfirmBillingAccountInfoView, self).post(request, *args, **kwargs)

    def send_downgrade_email(self):
        message = '\n'.join([
            '{user} is downgrading the subscription for {domain} from {old_plan} to {new_plan}',
            '',
            '{note}',
        ]).format(
            user=self.request.couch_user.username,
            domain=self.request.domain,
            old_plan=self.request.POST.get('old_plan', 'unknown'),
            new_plan=self.request.POST.get('new_plan', 'unknown'),
            note=self.request.POST.get('downgrade_email_note', 'none')
        )
        send_mail_async.delay(
            '{}Subscription downgrade for {}'.format(
                '[staging] ' if settings.SERVER_ENVIRONMENT == "staging" else "",
                self.request.domain
            ), message, [settings.GROWTH_EMAIL]
        )

    def send_keep_subscription_email(self):
        message = '\n'.join([
            '{user} decided to keep their subscription for {domain} of {new_plan}',
        ]).format(
            user=self.request.couch_user.username,
            domain=self.request.domain,
            old_plan=self.request.POST.get('old_plan', 'unknown'),
        )

        send_mail_async.delay(
            '{}Subscription kept for {}'.format(
                '[staging] ' if settings.SERVER_ENVIRONMENT == "staging" else "",
                self.request.domain
            ), message, [settings.GROWTH_EMAIL]
        )


class SubscriptionMixin(object):

    @property
    @memoized
    def subscription(self):
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if subscription is None:
            raise Http404
        if subscription.is_renewed:
            raise Http404
        if subscription.plan_version.is_paused:
            raise Http404
        return subscription


class SubscriptionRenewalView(SelectPlanView, SubscriptionMixin):
    urlname = "domain_subscription_renewal"
    page_title = gettext_lazy("Renew Plan")
    step_title = gettext_lazy("Renew Plan")
    template_name = "domain/renew_plan.html"

    @property
    def lead_text(self):
        return format_html(
            _("Based on your current usage we recommend you use the <strong>{plan}</strong> plan"),
            plan=_(self.current_subscription.plan_version.plan.edition)
        )

    @property
    def page_context(self):
        context = super(SubscriptionRenewalView, self).page_context

        current_edition = self.subscription.plan_version.plan.edition

        if current_edition in [
            SoftwarePlanEdition.COMMUNITY,
            SoftwarePlanEdition.PAUSED,
        ]:
            raise Http404()

        context.update({
            'current_edition': current_edition,
            'plan': self.subscription.plan_version.user_facing_description,
            'tile_css': 'tile-{}'.format(current_edition.lower()),
            'is_renewal_page': True,
        })
        return context


class ConfirmSubscriptionRenewalView(SelectPlanView, DomainAccountingSettings,
                                     AsyncHandlerMixin, SubscriptionMixin):
    template_name = 'domain/confirm_subscription_renewal.html'
    urlname = 'domain_subscription_renewal_confirmation'
    page_title = gettext_lazy("Confirm Billing Information")
    step_title = gettext_lazy("Confirm Billing Information")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    def is_request_from_current_step(self):
        return self.request.method == 'POST' and "from_plan_page" not in self.request.POST

    @method_decorator(require_POST)
    def dispatch(self, request, *args, **kwargs):
        return super(ConfirmSubscriptionRenewalView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def next_plan_version(self):
        plan_version = DefaultProductPlan.get_default_plan_version(self.new_edition)
        if plan_version is None:
            try:
                # needed for sending to sentry
                raise SubscriptionRenewalError()
            except SubscriptionRenewalError:
                log_accounting_error(
                    f"Could not find a matching renewable plan "
                    f"for {self.domain}, "
                    f"subscription number {self.subscription.pk}."
                )
            raise Http404
        return plan_version

    @property
    @memoized
    def confirm_form(self):
        if self.is_request_from_current_step:
            return ConfirmSubscriptionRenewalForm(
                self.account, self.domain, self.request.couch_user.username,
                self.subscription, self.next_plan_version,
                data=self.request.POST,
            )
        return ConfirmSubscriptionRenewalForm(
            self.account, self.domain, self.request.couch_user.username,
            self.subscription, self.next_plan_version,
        )

    @property
    def page_context(self):
        return {
            'subscription': self.subscription,
            'plan': self.subscription.plan_version.user_facing_description,
            'confirm_form': self.confirm_form,
            'next_plan': self.next_plan_version.user_facing_description,
            'is_renewal_page': True,
        }

    @property
    def new_edition(self):
        return self.request.POST.get('plan_edition').title()

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.new_edition == SoftwarePlanEdition.ENTERPRISE:
            return HttpResponseRedirect(reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]))
        if (not self.is_request_from_current_step
                and self.new_edition not in SoftwarePlanEdition.SELF_RENEWABLE_EDITIONS):
            messages.error(
                request,
                _("Your subscription is not eligible for self-renewal. "
                  "Please sign up for a new subscription instead or contact {}"
                  ).format(settings.BILLING_EMAIL)
            )
            return HttpResponseRedirect(
                reverse(DomainSubscriptionView.urlname, args=[self.domain])
            )
        if self.confirm_form.is_valid():
            is_saved = self.confirm_form.save()
            if not is_saved:
                messages.error(
                    request, _(
                        "There was an issue renewing your subscription. We "
                        "have been notified of the issue. Please try "
                        "submitting again, and if the problem persists, "
                        "please try in a few hours."
                    )
                )
            else:
                messages.success(
                    request, _("Your subscription was successfully renewed!")
                )
                return HttpResponseRedirect(
                    reverse(DomainSubscriptionView.urlname, args=[self.domain])
                )
        return self.get(request, *args, **kwargs)


class EmailOnDowngradeView(View):
    urlname = "email_on_downgrade"

    def post(self, request, *args, **kwargs):
        message = '\n'.join([
            '{user} is downgrading the subscription for {domain} from {old_plan} to {new_plan}.',
            '',
            'Note from user: {note}',
        ]).format(
            user=request.couch_user.username,
            domain=request.domain,
            old_plan=request.POST.get('old_plan', 'unknown'),
            new_plan=request.POST.get('new_plan', 'unknown'),
            note=request.POST.get('note', 'none'),
        )

        send_mail_async.delay(
            '{}Subscription downgrade for {}'.format(
                '[staging] ' if settings.SERVER_ENVIRONMENT == "staging" else "",
                request.domain
            ), message, [settings.GROWTH_EMAIL]
        )
        return json_response({'success': True})


class BaseCardView(DomainAccountingSettings):

    @property
    def payment_method(self):
        payment_method, __ = StripePaymentMethod.objects.get_or_create(
            web_user=self.request.user.username,
            method_type=PaymentMethodType.STRIPE,
        )
        return payment_method

    def _generic_error(self):
        error = ("Something went wrong while processing your request. "
                 "We're working quickly to resolve the issue. "
                 "Please try again in a few hours.")
        return json_response({'error': error}, status_code=500)

    def _stripe_error(self, e):
        body = e.json_body
        err = body['error']
        return json_response({'error': err['message'],
                              'cards': self.payment_method.all_cards_serialized(self.account)},
                             status_code=502)


class CardView(BaseCardView):
    """View for dealing with a single Credit Card"""
    url_name = "card_view"

    def post(self, request, domain, card_token):
        try:
            card = self.payment_method.get_card(card_token)
            if request.POST.get("is_autopay") == 'true':
                self.payment_method.set_autopay(card, self.account, domain)
            elif request.POST.get("is_autopay") == 'false':
                self.payment_method.unset_autopay(card, self.account)
        except self.payment_method.STRIPE_GENERIC_ERROR as e:
            return self._stripe_error(e)
        except Exception:
            return self._generic_error()

        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})

    def delete(self, request, domain, card_token):
        try:
            self.payment_method.remove_card(card_token)
        except self.payment_method.STRIPE_GENERIC_ERROR as e:
            return self._stripe_error(e)

        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})


class CardsView(BaseCardView):
    """View for dealing Credit Cards"""
    url_name = "cards_view"

    def get(self, request, domain):
        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})

    def post(self, request, domain):
        stripe_token = request.POST.get('token')
        autopay = request.POST.get('autopay') == 'true'
        try:
            self.payment_method.create_card(stripe_token, self.account, domain, autopay)
        except self.payment_method.STRIPE_GENERIC_ERROR as e:
            return self._stripe_error(e)
        except Exception:
            return self._generic_error()

        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})


def _get_downgrade_or_pause_note(request, is_pause=False):
    downgrade_reason = request.POST.get('downgrade_reason')
    will_project_restart = request.POST.get('will_project_restart')
    new_tool = request.POST.get('new_tool')
    new_tool_reason = request.POST.get('new_tool_reason')
    feedback = request.POST.get('feedback')
    if not downgrade_reason:
        return None
    return "\n".join([
        "Why are you {method} your subscription today?\n{reason}\n",
        "Do you think your project may start again?\n{will_project_restart}\n",
        "Could you indicate which new tool you are using?\n{new_tool}\n",
        "Why are you switching to a new tool?\n{new_tool_reason}\n",
        "Additional feedback:\n{feedback}\n\n"
    ]).format(
        method="pausing" if is_pause else "downgrading",
        reason=downgrade_reason,
        will_project_restart=will_project_restart,
        new_tool=new_tool,
        new_tool_reason=new_tool_reason,
        feedback=feedback,
    )


@require_POST
@login_and_domain_required
@require_permission(HqPermissions.edit_billing)
def pause_subscription(request, domain):
    current_subscription = Subscription.get_active_subscription_by_domain(domain)
    if not current_subscription.user_can_change_subscription(request.user):
        messages.error(
            request, _(
                "You do not have permission to pause the subscription for this customer-level account. "
                "Please reach out to the %s enterprise admin for help."
            ) % current_subscription.account.name
        )
        return HttpResponseRedirect(
            reverse(DomainSubscriptionView.urlname, args=[domain])
        )

    try:
        with transaction.atomic():
            paused_subscription = pause_current_subscription(
                domain, request.couch_user.username, current_subscription
            )
            pause_message = '\n'.join([
                "{user} is pausing the subscription for {domain} from {old_plan}\n",
                "{note}"
            ]).format(
                user=request.couch_user.username,
                domain=domain,
                old_plan=current_subscription.plan_version.plan.edition,
                note=_get_downgrade_or_pause_note(request, True),
            )

            send_mail_async.delay(
                "{}Subscription pausing for {}".format(
                    '[staging] ' if settings.SERVER_ENVIRONMENT == "staging" else "",
                    domain,
                ), pause_message, [settings.GROWTH_EMAIL]
            )

            if current_subscription.is_below_minimum_subscription:
                messages.success(request, _(
                    "Your project's subscription will be paused on {}. "
                    "We hope to see you again!"
                ).format(paused_subscription.date_start.strftime(USER_DATE_FORMAT)))
            else:
                messages.success(
                    request, _("Your project's subscription has now been paused. "
                               "We hope to see you again!")
                )
    except Exception as e:
        log_accounting_error(
            "There was an error pausing the subscription for the domain '{}'. "
            "Message: {}".format(domain, str(e)),
            show_stack_trace=True
        )
        messages.error(
            request, _("We were not able to pause your subscription at this time. "
                       "Please contact {} if you continue to receive this error. "
                       "We apologize for the inconvenience.").format(
                settings.BILLING_EMAIL,
            )
        )

    return HttpResponseRedirect(
        reverse(DomainSubscriptionView.urlname, args=[domain])
    )
