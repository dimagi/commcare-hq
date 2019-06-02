from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date
import json
import six

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Sum
from django.forms.forms import NON_FIELD_ERRORS
from django.forms.utils import ErrorList
from django.urls import reverse
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseRedirect,
    Http404,
    JsonResponse,
)
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from django.views.decorators.http import require_POST
from django.views.generic import View

from couchexport.export import Format
from dimagi.utils.couch.cache.cache_core import get_redis_client
from couchdbkit import ResourceNotFound

from corehq.apps.domain.decorators import login_and_domain_required, require_superuser
from corehq.apps.domain.views.accounting import (
    BillingStatementPdfView,
    PAYMENT_ERROR_MESSAGES,
    InvoiceStripePaymentView,
    WireInvoiceView,
    BulkStripePaymentView,
    DomainAccountingSettings
)
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import (
    use_jquery_ui,
    use_multiselect,
)
from corehq.const import USER_DATE_FORMAT

import csv342 as csv
from memoized import memoized

from corehq.apps.accounting.enterprise import EnterpriseReport
from corehq.apps.accounting.forms import (
    BillingAccountBasicForm, BillingAccountContactForm, CreditForm,
    SubscriptionForm, CancelForm,
    PlanInformationForm, SoftwarePlanVersionForm, FeatureRateForm,
    ProductRateForm, TriggerInvoiceForm, InvoiceInfoForm, AdjustBalanceForm,
    ResendEmailForm, ChangeSubscriptionForm, TriggerBookkeeperEmailForm, TriggerCustomerInvoiceForm,
    TestReminderEmailFrom,
    CreateAdminForm,
    EnterpriseSettingsForm,
    SuppressInvoiceForm,
    SuppressSubscriptionForm,
    HideInvoiceForm,
    RemoveAutopayForm,
)
from corehq.apps.accounting.exceptions import (
    NewSubscriptionError, InvoiceError, CreditLineError,
    CreateAccountingAdminError,
    SubscriptionAdjustmentError,
)
from corehq.apps.accounting.interface import (
    AccountingInterface, SubscriptionInterface, SoftwarePlanInterface,
    InvoiceInterface, WireInvoiceInterface, CustomerInvoiceInterface
)
from corehq.apps.accounting.async_handlers import (
    FeatureRateAsyncHandler,
    Select2RateAsyncHandler,
    SoftwareProductRateAsyncHandler,
    Select2BillingInfoHandler,
    Select2InvoiceTriggerHandler,
    Select2CustomerInvoiceTriggerHandler,
    SubscriberFilterAsyncHandler,
    SubscriptionFilterAsyncHandler,
    AccountFilterAsyncHandler,
    DomainFilterAsyncHandler,
    BillingContactInfoAsyncHandler,
    SoftwarePlanAsyncHandler,
    InvoiceNumberAsyncHandler,
    InvoiceBalanceAsyncHandler,
)
from corehq.apps.accounting.models import (
    Invoice, WireInvoice, CustomerInvoice, BillingAccount, CreditLine, Subscription, CustomerBillingRecord,
    SoftwarePlanVersion, SoftwarePlan, CreditAdjustment, DefaultProductPlan, StripePaymentMethod, InvoicePdf
)
from corehq.apps.accounting.tasks import email_enterprise_report
from corehq.apps.accounting.utils import (
    fmt_feature_rate_dict, fmt_product_rate_dict,
    has_subscription_already_ended,
    log_accounting_error,
    quantize_accounting_decimal,
    get_customer_cards
)
from corehq.apps.hqwebapp.views import BaseSectionPageView, CRUDPaginatedViewMixin
from corehq import privileges
from django_prbac.decorators import requires_privilege_raise404
from django_prbac.models import Role, Grant
from django_prbac.utils import has_privilege

from six.moves.urllib.parse import urlencode


@require_superuser
@requires_privilege_raise404(privileges.ACCOUNTING_ADMIN)
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


class AccountingSectionView(BaseSectionPageView):
    section_name = 'Accounting'

    @property
    def section_url(self):
        return reverse('accounting_default')

    @method_decorator(require_superuser)
    @method_decorator(requires_privilege_raise404(privileges.ACCOUNTING_ADMIN))
    def dispatch(self, request, *args, **kwargs):
        return super(AccountingSectionView, self).dispatch(request, *args, **kwargs)


class BillingAccountsSectionView(AccountingSectionView):

    @property
    def parent_pages(self):
        return [{
            'title': AccountingInterface.name,
            'url': AccountingInterface.get_url(),
        }]


class NewBillingAccountView(BillingAccountsSectionView):
    page_title = 'New Billing Account'
    template_name = 'accounting/accounts_base.html'
    urlname = 'new_billing_account'

    @property
    @memoized
    def account_form(self):
        if self.request.method == 'POST':
            return BillingAccountBasicForm(None, self.request.POST)
        return BillingAccountBasicForm(None)

    @property
    def page_context(self):
        return {
            'basic_form': self.account_form,
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        if self.account_form.is_valid():
            account = self.account_form.create_account()
            return HttpResponseRedirect(reverse('manage_billing_account', args=(account.id,)))
        else:
            return self.get(request, *args, **kwargs)


class ManageBillingAccountView(BillingAccountsSectionView, AsyncHandlerMixin):
    page_title = 'Manage Billing Account'
    template_name = 'accounting/accounts.html'
    urlname = 'manage_billing_account'
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    @memoized
    def account(self):
        try:
            return BillingAccount.objects.get(id=self.args[0])
        except BillingAccount.DoesNotExist:
            raise Http404()

    @property
    @memoized
    def basic_account_form(self):
        if (self.request.method == 'POST'
                and 'account_basic' in self.request.POST):
            return BillingAccountBasicForm(self.account, self.request.POST)
        return BillingAccountBasicForm(self.account)

    @property
    @memoized
    def contact_form(self):
        if (self.request.method == 'POST'
                and 'account_contact' in self.request.POST):
            return BillingAccountContactForm(self.account, self.request.POST)
        return BillingAccountContactForm(self.account)

    @property
    @memoized
    def credit_form(self):
        if (self.request.method == 'POST'
                and 'adjust' in self.request.POST):
            return CreditForm(self.account, None, self.request.POST)
        return CreditForm(self.account, None)

    @property
    @memoized
    def remove_autopay_form(self):
        if self.request.method == 'POST' and 'remove_autopay' in self.request.POST:
            return RemoveAutopayForm(self.account, self.request.POST)
        return RemoveAutopayForm(self.account)

    @property
    def page_context(self):
        return {
            'account': self.account,
            'auto_pay_card': (
                StripePaymentMethod.objects.get(web_user=self.account.auto_pay_user).get_autopay_card(self.account)
                if self.account.auto_pay_enabled else None
            ),
            'credit_form': self.credit_form,
            'credit_list': CreditLine.objects.filter(account=self.account, is_active=True),
            'basic_form': self.basic_account_form,
            'contact_form': self.contact_form,
            'remove_autopay_form': self.remove_autopay_form,
            'subscription_list': [
                (
                    sub,
                    Invoice.objects.filter(subscription=sub).latest('date_due').date_due
                    if Invoice.objects.filter(subscription=sub).count() else 'None on record'
                )
                for sub in Subscription.visible_objects.filter(account=self.account).order_by(
                    'subscriber__domain', 'date_end'
                )
            ],
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.args[0],))

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if ('account_basic' in self.request.POST
                and self.basic_account_form.is_valid()):
            self.basic_account_form.update_basic_info(self.account)
            messages.success(request, "Account successfully updated.")
            return HttpResponseRedirect(self.page_url)
        elif ('account_contact' in self.request.POST
              and self.contact_form.is_valid()):
            self.contact_form.save()
            messages.success(request, "Account Contact Info successfully updated.")
            return HttpResponseRedirect(self.page_url)
        elif ('adjust' in self.request.POST
              and self.credit_form.is_valid()):
            try:
                if self.credit_form.adjust_credit(web_user=request.user.username):
                    messages.success(request, "Successfully adjusted credit.")
                    return HttpResponseRedirect(self.page_url)
            except CreditLineError as e:
                log_accounting_error(
                    "failed to add credit in admin UI due to: %s"
                    % e
                )
                messages.error(request, "Issue adding credit: %s" % e)
        elif 'remove_autopay' in self.request.POST:
            self.remove_autopay_form.remove_autopay_user_from_account()
            return HttpResponseRedirect(self.page_url)
        return self.get(request, *args, **kwargs)


class NewSubscriptionView(AccountingSectionView, AsyncHandlerMixin):
    page_title = 'New Subscription'
    template_name = 'accounting/subscriptions_base.html'
    urlname = 'new_subscription'
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @use_jquery_ui  # for datepicker
    def dispatch(self, request, *args, **kwargs):
        return super(NewSubscriptionView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def account_id(self):
        return self.args[0]

    @property
    @memoized
    def subscription_form(self):
        if self.request.method == 'POST':
            return SubscriptionForm(
                None, self.account_id, self.request.user.username,
                self.request.POST
            )
        return SubscriptionForm(None, self.account_id, None)

    @property
    def page_context(self):
        return {
            'form': self.subscription_form,
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.account_id,))

    @property
    def parent_pages(self):
        return [{
            'title': AccountingInterface.name,
            'url': AccountingInterface.get_url(),
        }]

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.subscription_form.is_valid():
            try:
                subscription = self.subscription_form.create_subscription()
                return HttpResponseRedirect(
                    reverse(EditSubscriptionView.urlname, args=(subscription.id,))
                )
            except NewSubscriptionError as e:
                errors = ErrorList()
                errors.extend([six.text_type(e)])
                self.subscription_form._errors.setdefault(NON_FIELD_ERRORS, errors)
        return self.get(request, *args, **kwargs)


class NewSubscriptionViewNoDefaultDomain(NewSubscriptionView):
    urlname = 'new_subscription_no_default_domain'

    @property
    @memoized
    def account_id(self):
        return None

    @property
    def page_url(self):
        return reverse(self.urlname)


class EditSubscriptionView(AccountingSectionView, AsyncHandlerMixin):
    page_title = 'Edit Subscription'
    template_name = 'accounting/subscriptions.html'
    urlname = 'edit_subscription'
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @use_jquery_ui  # for datepicker
    def dispatch(self, request, *args, **kwargs):
        return super(EditSubscriptionView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def subscription_id(self):
        return self.args[0]

    @property
    @memoized
    def subscription(self):
        try:
            return Subscription.visible_objects.get(id=self.subscription_id)
        except Subscription.DoesNotExist:
            raise Http404()

    @property
    @memoized
    def subscription_form(self):
        if self.request.method == 'POST' and 'set_subscription' in self.request.POST:
            return SubscriptionForm(
                self.subscription, None, self.request.user.username,
                self.request.POST
            )
        return SubscriptionForm(self.subscription, None, None)

    @property
    @memoized
    def change_subscription_form(self):
        if (self.request.method == 'POST'
           and 'subscription_change_note' in self.request.POST):
            return ChangeSubscriptionForm(
                self.subscription, self.request.user.username,
                self.request.POST
            )
        return ChangeSubscriptionForm(self.subscription,
                                      self.request.user.username)

    @property
    @memoized
    def credit_form(self):
        if self.request.method == 'POST' and 'adjust' in self.request.POST:
            return CreditForm(self.subscription.account, self.subscription,
                              self.request.POST)
        return CreditForm(self.subscription.account, self.subscription)

    @property
    @memoized
    def cancel_form(self):
        if (self.request.method == 'POST'
            and 'cancel_subscription' in self.request.POST):
            return CancelForm(self.subscription, self.request.POST)
        return CancelForm(self.subscription)

    @property
    @memoized
    def suppress_form(self):
        if self.request.method == 'POST' and 'suppress_subscription' in self.request.POST:
            return SuppressSubscriptionForm(self.subscription, self.request.POST)
        return SuppressSubscriptionForm(self.subscription)

    @property
    def invoice_context(self):
        subscriber_domain = self.subscription.subscriber.domain

        if self.subscription.account.is_customer_billing_account:
            invoice_report = CustomerInvoiceInterface(self.request)
            invoice_report.filter_by_account(self.subscription.account)
        else:
            invoice_report = InvoiceInterface(self.request)
            invoice_report.filter_by_subscription(self.subscription)
        # Tied to InvoiceInterface.
        encoded_params = urlencode({'subscriber': subscriber_domain})
        invoice_report_url = "{}?{}".format(invoice_report.get_url(), encoded_params)
        invoice_export_url = "{}?{}".format(invoice_report.get_url(render_as='export'), encoded_params)
        return {
            'invoice_headers': invoice_report.headers,
            'invoice_rows': invoice_report.rows,
            'invoice_export_url': invoice_export_url,
            'invoice_report_url': invoice_report_url,
            'adjust_balance_forms': invoice_report.adjust_balance_forms,
        }

    @property
    def page_context(self):
        context = {
            'cancel_form': self.cancel_form,
            'credit_form': self.credit_form,
            'can_change_subscription': self.subscription.is_active,
            'change_subscription_form': self.change_subscription_form,
            'credit_list': CreditLine.objects.filter(subscription=self.subscription, is_active=True),
            'disable_cancel': has_subscription_already_ended(self.subscription),
            'form': self.subscription_form,
            "subscription_has_ended": (
                not self.subscription.is_active
                and self.subscription.date_start <= date.today()
            ),
            'subscription': self.subscription,
            'subscription_canceled':
                self.subscription_canceled if hasattr(self, 'subscription_canceled') else False,
            'suppress_form': self.suppress_form,
        }

        context.update(self.invoice_context)
        return context

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.subscription_id,))

    @property
    def parent_pages(self):
        return [{
            'title': SubscriptionInterface.name,
            'url': SubscriptionInterface.get_url(),
        }]

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if 'set_subscription' in self.request.POST and self.subscription_form.is_valid():
            try:
                self.subscription_form.update_subscription()
                messages.success(request, "The subscription has been updated.")
            except Exception as e:
                messages.error(request,
                               "Could not update subscription due to: %s" % e)
            return HttpResponseRedirect(self.page_url)
        elif 'adjust' in self.request.POST and self.credit_form.is_valid():
            if self.credit_form.adjust_credit(web_user=request.user.username):
                return HttpResponseRedirect(self.page_url)
        elif ('cancel_subscription' in self.request.POST
              and self.cancel_form.is_valid()):
            self.cancel_subscription()
            messages.success(request, "The subscription has been cancelled.")
        elif SuppressSubscriptionForm.submit_kwarg in self.request.POST and self.suppress_form.is_valid():
            self.suppress_subscription()
            return HttpResponseRedirect(SubscriptionInterface.get_url())
        elif ('subscription_change_note' in self.request.POST
              and self.change_subscription_form.is_valid()
        ):
            try:
                new_sub = self.change_subscription_form.change_subscription()
                return HttpResponseRedirect(reverse(self.urlname, args=[new_sub.id]))
            except Exception as e:
                messages.error(request,
                               "Could not change subscription due to: %s" % e)
        return self.get(request, *args, **kwargs)

    def cancel_subscription(self):
        self.subscription.change_plan(
            new_plan_version=DefaultProductPlan.get_default_plan_version(),
            note=self.cancel_form.cleaned_data['note'],
            web_user=self.request.user.username,
        )
        self.subscription_canceled = True

    def suppress_subscription(self):
        if self.subscription.is_active:
            raise SubscriptionAdjustmentError(
                "Cannot suppress active subscription, id %d"
                % self.subscription.id
            )
        else:
            self.subscription.is_hidden_to_ops = True
            self.subscription.save()


class NewSoftwarePlanView(AccountingSectionView):
    page_title = 'New Software Plan'
    template_name = 'accounting/plans_base.html'
    urlname = 'new_software_plan'

    @property
    @memoized
    def plan_info_form(self):
        if self.request.method == 'POST':
            return PlanInformationForm(None, self.request.POST)
        return PlanInformationForm(None)

    @property
    def page_context(self):
        return {
            'plan_info_form': self.plan_info_form,
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def parent_pages(self):
        return [{
            'title': SoftwarePlanInterface.name,
            'url': SoftwarePlanInterface.get_url(),
        }]

    def post(self, request, *args, **kwargs):
        if self.plan_info_form.is_valid():
            plan = self.plan_info_form.create_plan()
            return HttpResponseRedirect(reverse(EditSoftwarePlanView.urlname, args=(plan.id,)))
        return self.get(request, *args, **kwargs)


class EditSoftwarePlanView(AccountingSectionView, AsyncHandlerMixin):
    template_name = 'accounting/plans.html'
    urlname = 'edit_software_plan'
    page_title = "Edit Software Plan"
    async_handlers = [
        Select2RateAsyncHandler,
        FeatureRateAsyncHandler,
        SoftwareProductRateAsyncHandler,
    ]

    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super(EditSoftwarePlanView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def plan(self):
        try:
            return SoftwarePlan.objects.get(id=self.args[0])
        except SoftwarePlan.DoesNotExist:
            raise Http404()

    @property
    @memoized
    def plan_info_form(self):
        if self.request.method == 'POST' and 'update_version' not in self.request.POST:
            return PlanInformationForm(self.plan, self.request.POST)
        return PlanInformationForm(self.plan)

    @property
    @memoized
    def software_plan_version_form(self):
        plan_version = self.plan.get_version()
        if self.request.method == 'POST' and 'update_version' in self.request.POST:
            return SoftwarePlanVersionForm(self.plan, plan_version, self.request.POST)
        initial = {
            'feature_rates': json.dumps([fmt_feature_rate_dict(r.feature, r)
                                         for r in plan_version.feature_rates.all()] if plan_version else []),
            'product_rates': json.dumps(
                [fmt_product_rate_dict(plan_version.product_rate.name, plan_version.product_rate)]
                if plan_version else []
            ),
            'role_slug': plan_version.role.slug if plan_version else None,
        }
        return SoftwarePlanVersionForm(self.plan, plan_version, initial=initial)

    @property
    def page_context(self):
        return {
            'plan_info_form': self.plan_info_form,
            'plan_version_form': self.software_plan_version_form,
            'feature_rate_form': FeatureRateForm(),
            'product_rate_form': ProductRateForm(),
            'plan_versions': SoftwarePlanVersion.objects.filter(plan=self.plan).order_by('-date_created')
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=self.args)

    @property
    def parent_pages(self):
        return [{
            'title': SoftwarePlanInterface.name,
            'url': SoftwarePlanInterface.get_url(),
        }]

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if 'update_version' in request.POST:
            if self.software_plan_version_form.is_valid():
                self.software_plan_version_form.save(request)
            else:
                for error_list in self.software_plan_version_form.errors.values():
                    for error in error_list:
                        messages.error(request, error)
        elif self.plan_info_form.is_valid():
            self.plan_info_form.update_plan(request, self.plan)
        return self.get(request, *args, **kwargs)


class ViewSoftwarePlanVersionView(AccountingSectionView):
    urlname = 'view_softwareplan_version'
    page_title = 'Plan Version'
    template_name = 'accounting/plan_version.html'

    @property
    @memoized
    def plan_version(self):
        try:
            return SoftwarePlanVersion.objects.get(plan=self.args[0], id=self.args[1])
        except SoftwarePlan.DoesNotExist:
            raise Http404()

    @property
    def page_context(self):
        return {
            'plan_versions': [self.plan_version],
            'plan_id': self.args[0],
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=self.args)



class TriggerInvoiceView(AccountingSectionView, AsyncHandlerMixin):
    urlname = 'accounting_trigger_invoice'
    page_title = "Trigger Invoice"
    template_name = 'accounting/trigger_invoice.html'
    async_handlers = [
        Select2InvoiceTriggerHandler,
    ]

    @property
    @memoized
    def trigger_form(self):
        if self.request.method == 'POST':
            return TriggerInvoiceForm(self.request.POST)
        return TriggerInvoiceForm()

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'trigger_form': self.trigger_form,
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.trigger_form.is_valid():
            try:
                self.trigger_form.trigger_invoice()
                messages.success(
                    request, "Successfully triggered invoices for domain %s."
                             % self.trigger_form.cleaned_data['domain'])
                return HttpResponseRedirect(reverse(self.urlname))
            except (CreditLineError, InvoiceError) as e:
                messages.error(request, "Error generating invoices: %s" % e, extra_tags='html')
        return self.get(request, *args, **kwargs)


class TriggerCustomerInvoiceView(AccountingSectionView, AsyncHandlerMixin):
    urlname = 'accounting_trigger_customer_invoice'
    page_title = 'Trigger Customer Invoice'
    template_name = 'accounting/trigger_customer_invoice.html'
    async_handlers = [
        Select2CustomerInvoiceTriggerHandler,
    ]

    @property
    @memoized
    def trigger_customer_invoice_form(self):
        if self.request.method == 'POST':
            return TriggerCustomerInvoiceForm(self.request.POST)
        return TriggerCustomerInvoiceForm()

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'trigger_customer_form': self.trigger_customer_invoice_form,
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.trigger_customer_invoice_form.is_valid():
            try:
                self.trigger_customer_invoice_form.trigger_customer_invoice()
                messages.success(
                    request,
                    "Successfully triggered invoices for Customer Billing Account %s."
                    % self.trigger_customer_invoice_form.cleaned_data['customer_account']
                )
            except (CreditLineError, InvoiceError) as e:
                messages.error(request, 'Error generating invoices: %s' % e, extra_tags='html')
        return self.get(request, *args, **kwargs)


class TriggerBookkeeperEmailView(AccountingSectionView):
    urlname = 'accounting_trigger_bookkeeper_email'
    page_title = "Trigger Bookkeeper Email"
    template_name = 'accounting/trigger_bookkeeper.html'

    @property
    @memoized
    def trigger_email_form(self):
        if self.request.method == 'POST':
            return TriggerBookkeeperEmailForm(self.request.POST)
        return TriggerBookkeeperEmailForm()

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'trigger_email_form': self.trigger_email_form,
        }

    def post(self, request, *args, **kwargs):
        if self.trigger_email_form.is_valid():
            self.trigger_email_form.trigger_email()
            messages.success(request, "Sent the Bookkeeper email!")
            return HttpResponseRedirect(reverse(self.urlname))
        return self.get(request, *args, **kwargs)


class TestRenewalEmailView(AccountingSectionView):
    urlname = 'accounting_test_renewal_email'
    page_title = "Test Renewal Reminder Email"
    template_name = 'accounting/test_reminder_emails.html'

    @property
    @memoized
    def reminder_email_form(self):
        if self.request.method == 'POST':
            return TestReminderEmailFrom(self.request.POST)
        return TestReminderEmailFrom()

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'reminder_email_form': self.reminder_email_form,
        }

    def post(self, request, *args, **kwargs):
        if self.reminder_email_form.is_valid():
            self.reminder_email_form.send_emails()
            messages.success(request, "Sent the Reminder emails!")
            return HttpResponseRedirect(reverse(self.urlname))
        return self.get(request, *args, **kwargs)


class InvoiceSummaryViewBase(AccountingSectionView):
    template_name = 'accounting/invoice.html'

    @property
    @memoized
    def invoice(self):
        try:
            return self.invoice_class.objects.get(id=self.args[0])
        except self.invoice_class.DoesNotExist:
            raise Http404()

    @property
    def page_title(self):
        return "Invoice #%s" % self.invoice.invoice_number

    @property
    def page_url(self):
        return reverse(self.urlname, args=self.args)

    @property
    def page_context(self):
        return {
            'billing_records': [
                {
                    'date_created': billing_record.date_created,
                    'email_recipients': ', '.join(billing_record.emailed_to_list),
                    'invoice': billing_record.invoice,
                    'pdf_data_id': billing_record.pdf_data_id,
                }
                for billing_record in self.billing_records if not billing_record.skipped_email
            ],
            'can_send_email': self.can_send_email,
            'invoice_info_form': self.invoice_info_form,
            'resend_email_form': self.resend_email_form,
            'suppress_invoice_form': self.suppress_invoice_form,
            'hide_invoice_form': self.hide_invoice_form,
        }

    @property
    @memoized
    def billing_records(self):
        raise NotImplementedError

    @property
    def can_send_email(self):
        raise NotImplementedError

    @property
    @memoized
    def resend_email_form(self):
        if self.request.method == 'POST':
            return ResendEmailForm(self.invoice, self.request.POST)
        return ResendEmailForm(self.invoice)

    @property
    @memoized
    def invoice_info_form(self):
        return InvoiceInfoForm(self.invoice)

    @property
    @memoized
    def suppress_invoice_form(self):
        if self.request.method == 'POST':
            return SuppressInvoiceForm(self.invoice, self.request.POST)
        return SuppressInvoiceForm(self.invoice)

    @property
    @memoized
    def hide_invoice_form(self):
        if self.request.method == 'POST':
            return HideInvoiceForm(self.invoice, self.request.POST)
        return HideInvoiceForm(self.invoice)

    def post(self, request, *args, **kwargs):
        if 'adjust' in self.request.POST:
            if self.adjust_balance_form.is_valid():
                self.adjust_balance_form.adjust_balance(
                    web_user=self.request.user.username,
                )
                return HttpResponseRedirect(request.META.get('HTTP_REFERER') or self.page_url)
        elif 'resend' in self.request.POST:
            if self.resend_email_form.is_valid():
                try:
                    self.resend_email_form.resend_email()
                    return HttpResponseRedirect(self.page_url)
                except Exception as e:
                    messages.error(request,
                                   "Could not send emails due to: %s" % e)
        elif SuppressInvoiceForm.submit_kwarg in self.request.POST:
            if self.suppress_invoice_form.is_valid():
                self.suppress_invoice_form.suppress_invoice()
                if self.invoice.is_customer_invoice:
                    return HttpResponseRedirect(CustomerInvoiceInterface.get_url())
                else:
                    return HttpResponseRedirect(InvoiceInterface.get_url())
        elif HideInvoiceForm.submit_kwarg in self.request.POST:
            if self.hide_invoice_form.is_valid():
                self.hide_invoice_form.hide_invoice()
        return self.get(request, *args, **kwargs)


class WireInvoiceSummaryView(InvoiceSummaryViewBase):
    urlname = 'wire_invoice_summary'
    invoice_class = WireInvoice

    @property
    def parent_pages(self):
        return [{
            'title': WireInvoiceInterface.name,
            'url': WireInvoiceInterface.get_url(),
        }]

    @property
    @memoized
    def billing_records(self):
        return self.invoice.wirebillingrecord_set.all()

    @property
    def can_send_email(self):
        return True


class InvoiceSummaryView(InvoiceSummaryViewBase):
    urlname = 'invoice_summary'
    invoice_class = Invoice

    @property
    def parent_pages(self):
        return [{
            'title': InvoiceInterface.name,
            'url': InvoiceInterface.get_url(),
        }]

    @property
    @memoized
    def adjust_balance_form(self):
        if self.request.method == 'POST':
            return AdjustBalanceForm(self.invoice, self.request.POST)
        return AdjustBalanceForm(self.invoice)

    @property
    @memoized
    def billing_records(self):
        return self.invoice.billingrecord_set.all()

    @property
    @memoized
    def adjustment_list(self):
        adjustment_list = CreditAdjustment.objects.filter(invoice=self.invoice)
        return adjustment_list.order_by('-date_created')

    @property
    def can_send_email(self):
        return not self.invoice.subscription.do_not_invoice

    @property
    def page_context(self):
        context = super(InvoiceSummaryView, self).page_context
        context.update({
            'adjust_balance_form': self.adjust_balance_form,
            'adjustment_list': self.adjustment_list,
        })
        return context


class CustomerInvoiceSummaryView(InvoiceSummaryViewBase):
    urlname = 'customer_invoice_summary'
    invoice_class = CustomerInvoice

    @property
    def parent_pages(self):
        return [{
            'title': CustomerInvoiceInterface.name,
            'url': CustomerInvoiceInterface.get_url()
        }]

    @property
    @memoized
    def adjust_balance_form(self):
        if self.request.method == 'POST':
            return AdjustBalanceForm(self.invoice, self.request.POST)
        return AdjustBalanceForm(self.invoice)

    @property
    @memoized
    def billing_records(self):
        return self.invoice.customerbillingrecord_set.all()

    @property
    @memoized
    def adjustment_list(self):
        adjustment_list = CreditAdjustment.objects.filter(customer_invoice=self.invoice)
        return adjustment_list.order_by('-date_created')

    @property
    def can_send_email(self):
        return True

    @property
    def page_context(self):
        context = super(CustomerInvoiceSummaryView, self).page_context
        context.update({
            'adjust_balance_form': self.adjust_balance_form,
            'adjustment_list': self.adjustment_list
        })
        return context


class CustomerInvoicePdfView(View):
    urlname = 'invoice_pdf_view'

    def dispatch(self, request, *args, **kwargs):
        return super(CustomerInvoicePdfView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        statement_id = kwargs.get('statement_id')
        if statement_id is None:
            raise Http404()
        try:
            invoice_pdf = InvoicePdf.get(statement_id)
        except ResourceNotFound:
            raise Http404()

        try:
            if not invoice_pdf.is_customer:
                raise NotImplementedError
            else:
                invoice = CustomerInvoice.objects.get(pk=invoice_pdf.invoice_id)
        except (Invoice.DoesNotExist, WireInvoice.DoesNotExist, CustomerInvoice.DoesNotExist):
            raise Http404()

        filename = "%(pdf_id)s_%(edition)s_%(filename)s" % {
            'pdf_id': invoice_pdf._id,
            'edition': 'customer',
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


class ManageAccountingAdminsView(AccountingSectionView, CRUDPaginatedViewMixin):
    template_name = 'accounting/accounting_admins.html'
    urlname = 'accounting_manage_admins'
    page_title = ugettext_noop("Accounting Admins")

    limit_text = ugettext_noop("Admins per page")
    empty_notification = ugettext_noop("You haven't specified any accounting admins. "
                                       "How are you viewing this page??! x_x")
    loading_message = ugettext_noop("Loading admin list...")
    deleted_items_header = ugettext_noop("Removed Users:")
    new_items_header = ugettext_noop("Added Users:")

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def accounting_admin_queryset(self):
        return User.objects.filter(
            prbac_role__role__memberships_granted__to_role__slug=privileges.OPERATIONS_TEAM
        )

    def paginated_admins(self):
        return Paginator(self.accounting_admin_queryset, self.limit)

    @property
    @memoized
    def total(self):
        return self.accounting_admin_queryset.count()

    @property
    def column_names(self):
        return [
            _('Username'),
            _('Action'),
        ]

    @property
    def paginated_list(self):
        for admin in self.paginated_admins().page(self.page):
            yield {
                'itemData': self._fmt_admin_data(admin),
                'template': 'accounting-admin-row',
            }

    @staticmethod
    def _fmt_admin_data(admin):
        return {
            'id': admin.id,
            'username': admin.username,
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return CreateAdminForm(self.request.POST)
        return CreateAdminForm()

    def get_create_item_data(self, create_form):
        try:
            user = create_form.add_admin_user()
        except CreateAccountingAdminError as e:
            return {
                'error': "Could Not Add to Admins: %s" % e,
            }
        return {
            'itemData': self._fmt_admin_data(user),
            'template': 'accounting-admin-new',
        }

    def get_deleted_item_data(self, item_id):
        user = User.objects.get(id=item_id)
        ops_role = Role.objects.get(slug=privileges.OPERATIONS_TEAM)
        grant_to_remove = Grant.objects.filter(
            from_role=user.prbac_role.role,
            to_role=ops_role,
        )
        grant_to_remove.delete()
        return {
            'deletedItem': self._fmt_admin_data(user),
            'template': 'accounting-admin-removed',
        }

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


class AccountingSingleOptionResponseView(View, AsyncHandlerMixin):
    urlname = 'accounting_subscriber_response'
    http_method_names = ['post']
    async_handlers = [
        SubscriberFilterAsyncHandler,
        SubscriptionFilterAsyncHandler,
        AccountFilterAsyncHandler,
        DomainFilterAsyncHandler,
        BillingContactInfoAsyncHandler,
        SoftwarePlanAsyncHandler,
        InvoiceNumberAsyncHandler,
        InvoiceBalanceAsyncHandler,
    ]

    @method_decorator(require_superuser)
    @method_decorator(requires_privilege_raise404(privileges.ACCOUNTING_ADMIN))
    def dispatch(self, request, *args, **kwargs):
        return super(AccountingSingleOptionResponseView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.async_response:
            return self.async_response
        return HttpResponseBadRequest("Please check your query.")


def _get_account_or_404(request, domain):
    account = BillingAccount.get_account_by_domain(domain)

    if account is None:
        raise Http404()

    if not account.has_enterprise_admin(request.couch_user.username):
        if not has_privilege(request, privileges.ACCOUNTING_ADMIN):
            raise Http404()

    return account


@login_and_domain_required
def enterprise_dashboard(request, domain):
    account = _get_account_or_404(request, domain)
    context = {
        'account': account,
        'domain': domain,
        'reports': [EnterpriseReport.create(slug, account.id, request.couch_user) for slug in (
            EnterpriseReport.DOMAINS,
            EnterpriseReport.WEB_USERS,
            EnterpriseReport.MOBILE_USERS,
            EnterpriseReport.FORM_SUBMISSIONS,
        )],
        'current_page': {
            'page_name': _('Enterprise Dashboard'),
            'title': _('Enterprise Dashboard'),
        }
    }
    return render(request, "accounting/enterprise_dashboard.html", context)


@login_and_domain_required
def enterprise_dashboard_total(request, domain, slug):
    account = _get_account_or_404(request, domain)
    report = EnterpriseReport.create(slug, account.id, request.couch_user)
    return JsonResponse({'total': report.total})


@login_and_domain_required
def enterprise_dashboard_download(request, domain, slug, export_hash):
    account = _get_account_or_404(request, domain)
    report = EnterpriseReport.create(slug, account.id, request.couch_user)

    redis = get_redis_client()
    content = redis.get(export_hash)

    if content:
        file = ContentFile(content)
        response = HttpResponse(file, Format.FORMAT_DICT[Format.UNZIPPED_CSV])
        response['Content-Length'] = file.size
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(report.filename)
        return response

    return HttpResponseNotFound(_("That report was not found. Please remember that "
                                  "download links expire after 24 hours."))


@login_and_domain_required
def enterprise_dashboard_email(request, domain, slug):
    account = _get_account_or_404(request, domain)
    report = EnterpriseReport.create(slug, account.id, request.couch_user)
    email_enterprise_report.delay(domain, slug, request.couch_user)
    message = _("Generating {title} report, will email to {email} when complete.").format(**{
        'title': report.title,
        'email': request.couch_user.username,
    })
    return JsonResponse({'message': message})


@login_and_domain_required
def enterprise_settings(request, domain):
    account = _get_account_or_404(request, domain)

    if request.method == 'POST':
        form = EnterpriseSettingsForm(request.POST, domain=domain, account=account)
    else:
        form = EnterpriseSettingsForm(domain=domain, account=account)

    context = {
        'account': account,
        'accounts_email': settings.ACCOUNTS_EMAIL,
        'domain': domain,
        'restrict_signup': request.POST.get('restrict_signup', account.restrict_signup),
        'current_page': {
            'title': _('Enterprise Settings'),
            'page_name': _('Enterprise Settings'),
        },
        'settings_form': form,
    }
    return render(request, "accounting/enterprise_settings.html", context)


@login_and_domain_required
@require_POST
def edit_enterprise_settings(request, domain):
    account = _get_account_or_404(request, domain)
    form = EnterpriseSettingsForm(request.POST, domain=domain, account=account)

    if form.is_valid():
        form.save(account)
        messages.success(request, "Account successfully updated.")
    else:
        return enterprise_settings(request, domain)

    return HttpResponseRedirect(reverse('enterprise_settings', args=[domain]))


class EnterpriseBillingStatementsView(DomainAccountingSettings, CRUDPaginatedViewMixin):
    template_name = 'domain/billing_statements.html'
    urlname = 'enterprise_billing_statements'
    page_title = ugettext_lazy("Billing Statements")

    limit_text = ugettext_lazy("statements per page")
    empty_notification = ugettext_lazy("No Billing Statements match the current criteria.")
    loading_message = ugettext_lazy("Loading statements...")

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def stripe_cards(self):
        return get_customer_cards(self.request.user.username, self.domain)

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
        account = self.account or _get_account_or_404(self.request, self.request.domain)
        invoices = CustomerInvoice.objects.filter(account=account)
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
        account = self.account or _get_account_or_404(self.request, self.request.domain)
        invoices = (CustomerInvoice.objects
                    .filter(account=account)
                    .filter(date_paid__exact=None)
                    .filter(is_hidden=False))
        return invoices.aggregate(
            total_balance=Sum('balance')
        ).get('total_balance') or 0.00

    @property
    def column_names(self):
        return [
            _("Statement No."),
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
            'show_plan': False
        })
        return pagination_context

    @property
    def can_pay_invoices(self):
        return self.request.couch_user.is_domain_admin(self.domain)

    @property
    def paginated_list(self):
        for invoice in self.paginated_invoices.page(self.page).object_list:
            try:
                last_billing_record = CustomerBillingRecord.objects.filter(
                    invoice=invoice
                ).latest('date_created')
                if invoice.is_paid:
                    payment_status = (_("Paid on %s.")
                                      % invoice.date_paid.strftime(USER_DATE_FORMAT))
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
                        'plan': None,
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
            except CustomerBillingRecord.DoesNotExist:
                log_accounting_error(
                    "An invoice was generated for %(invoice_id)d "
                    "(domain: %(domain)s), but no billing record!" % {
                        'invoice_id': invoice.id,
                        'domain': self.domain,
                    }
                )

    def refresh_item(self, item_id):
        pass

    def post(self, *args, **kwargs):
        return self.paginate_crud_response
