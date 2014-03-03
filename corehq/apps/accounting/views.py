import json
import datetime

from django.conf import settings
from django.contrib import messages
from django.forms.forms import NON_FIELD_ERRORS
from django.forms.util import ErrorList
from django.utils import translation
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.accounting.forms import (BillingAccountForm, CreditForm, SubscriptionForm, CancelForm,
                                          PlanInformationForm, SoftwarePlanVersionForm, FeatureRateForm,
                                          ProductRateForm)
from corehq.apps.accounting.exceptions import NewSubscriptionError
from corehq.apps.accounting.interface import AccountingInterface, SubscriptionInterface, SoftwarePlanInterface
from corehq.apps.accounting.models import (SoftwareProductType, Invoice, BillingAccount, CreditLine, Subscription,
                                           SoftwarePlanVersion, SoftwarePlan)
from corehq.apps.accounting.async_handlers import (FeatureRateAsyncHandler, Select2RateAsyncHandler,
                                                   SoftwareProductRateAsyncHandler, Select2BillingInfoHandler,
                                                   Select2SubscriptionInfoHandler)
from corehq.apps.accounting.user_text import PricingTable
from corehq.apps.accounting.utils import LazyEncoder, fmt_feature_rate_dict, fmt_product_rate_dict
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq import toggles, privileges
from django_prbac.decorators import requires_privilege_raise404


@requires_privilege_raise404(privileges.ACCOUNTING_ADMIN)
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


class AccountingSectionView(BaseSectionPageView):
    section_name = 'Accounting'

    @property
    def section_url(self):
        return reverse('accounting_default')

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
            return BillingAccountForm(None, self.request.POST)
        return BillingAccountForm(None)

    @property
    def page_context(self):
        return {
            'form': self.account_form,
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
        return BillingAccount.objects.get(id=self.args[0])

    @property
    @memoized
    def account_form(self):
        if self.request.method == 'POST' and 'account' in self.request.POST:
            return BillingAccountForm(self.account, self.request.POST)
        return BillingAccountForm(self.account)

    @property
    @memoized
    def credit_form(self):
        if self.request.method == 'POST' and 'adjust_credit' in self.request.POST:
            return CreditForm(self.account.id, True, self.request.POST)
        return CreditForm(self.account.id, True)

    def get_appropriate_credit_form(self, account):
        if (not self.credit_form.is_bound) or (not self.credit_form.is_valid()):
            return self.credit_form
        return CreditForm(account.id, True)

    @property
    def page_context(self):
        return {
            'account': self.account,
            'credit_form': self.get_appropriate_credit_form(self.account),
            'credit_list': CreditLine.objects.filter(account=self.account),
            'form': self.account_form,
            'subscription_list': [
                (sub, Invoice.objects.filter(subscription=sub).latest('date_due').date_due # TODO - check query
                      if len(Invoice.objects.filter(subscription=sub)) != 0 else 'None on record',
                ) for sub in Subscription.objects.filter(account=self.account)
            ],
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.args[0],))

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if 'account' in self.request.POST and self.account_form.is_valid():
            self.account_form.update_account_and_contacts(self.account)
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            self.credit_form.adjust_credit(account=self.account)

        return self.get(request, *args, **kwargs)


class NewSubscriptionView(AccountingSectionView, AsyncHandlerMixin):
    page_title = 'New Subscription'
    template_name = 'accounting/subscriptions_base.html'
    urlname = 'new_subscription'
    async_handlers = [
        Select2SubscriptionInfoHandler,
    ]

    @property
    @memoized
    def account_id(self):
        return self.args[0]

    @property
    @memoized
    def subscription_form(self):
        if self.request.method == 'POST':
            return SubscriptionForm(None, self.account_id, self.request.POST)
        return SubscriptionForm(None, self.account_id)

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
                   reverse(ManageBillingAccountView.urlname, args=(subscription.account.id,)))
            except NewSubscriptionError as e:
                errors = ErrorList()
                errors.extend([e.message])
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


class EditSubscriptionView(AccountingSectionView):
    page_title = 'Edit Subscription'
    template_name = 'accounting/subscriptions.html'
    urlname = 'edit_subscription'

    @property
    @memoized
    def subscription_id(self):
        return self.args[0]

    @property
    @memoized
    def subscription(self):
        return Subscription.objects.get(id=self.subscription_id)

    @property
    @memoized
    def subscription_form(self):
        if self.request.method == 'POST' and 'set_subscription' in self.request.POST:
            return SubscriptionForm(self.subscription, None, self.request.POST)
        return SubscriptionForm(self.subscription, None)

    def get_appropriate_subscription_form(self, subscription):
        if (not self.subscription_form.is_bound) or (not self.subscription_form.is_valid()):
            return self.subscription_form
        return SubscriptionForm(subscription, None)

    @property
    @memoized
    def credit_form(self):
        if self.request.method == 'POST' and 'adjust_credit' in self.request.POST:
            return CreditForm(self.subscription_id, False, self.request.POST)
        return CreditForm(self.subscription_id, False)

    def get_appropriate_credit_form(self, subscription):
        if (not self.credit_form.is_bound) or (not self.credit_form.is_valid()):
            return self.credit_form
        return CreditForm(subscription.id, False)

    @property
    def page_context(self):
        return {
            'cancel_form': CancelForm(),
            'credit_form': self.get_appropriate_credit_form(self.subscription),
            'credit_list': CreditLine.objects.filter(subscription=self.subscription),
            'form': self.get_appropriate_subscription_form(self.subscription),
            'subscription': self.subscription,
            'subscription_canceled': self.subscription_canceled if hasattr(self, 'subscription_canceled') else False,
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.args[0],))

    @property
    def parent_pages(self):
        return [{
            'title': SubscriptionInterface.name,
            'url': SubscriptionInterface.get_url(),
        }]

    def post(self, request, *args, **kwargs):
        if 'set_subscription' in self.request.POST and self.subscription_form.is_valid():
            new_subscription = self.subscription_form.update_subscription(self.subscription)
            return HttpResponseRedirect(reverse(self.urlname, args=(unicode(new_subscription.id),)))
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            self.credit_form.adjust_credit(subscription=self.subscription)
        elif 'cancel_subscription' in self.request.POST:
            self.cancel_subscription()
        return self.get(request, *args, **kwargs)

    def cancel_subscription(self):
        self.subscription.cancel_subscription()
        self.subscription_canceled = True


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

    @property
    @memoized
    def plan(self):
        return SoftwarePlan.objects.get(id=self.args[0])

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
        initial = {
            'feature_rates': json.dumps([fmt_feature_rate_dict(r.feature, r)
                                         for r in plan_version.feature_rates.all()] if plan_version else []),
            'product_rates': json.dumps([fmt_product_rate_dict(r.product, r)
                                         for r in plan_version.product_rates.all()] if plan_version else []),
            'role_slug': plan_version.role.slug if plan_version else None,
        }
        if self.request.method == 'POST' and 'update_version' in self.request.POST:
            return SoftwarePlanVersionForm(self.plan, self.plan.get_version(), self.request.POST, initial=initial)
        return SoftwarePlanVersionForm(self.plan, self.plan.get_version(), initial=initial)

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
                return HttpResponseRedirect(self.page_url)
        elif self.plan_info_form.is_valid():
            self.plan_info_form.update_plan(self.plan)
            messages.success(request, "The %s Software Plan was successfully updated." % self.plan.name)
        return self.get(request, *args, **kwargs)


def pricing_table_json(request, product, locale):
    if product not in [c[0] for c in SoftwareProductType.CHOICES]:
        return HttpResponseBadRequest("Not a valid product")
    if locale not in [l[0] for l in settings.LANGUAGES]:
        return HttpResponseBadRequest("Not a supported language.")
    translation.activate(locale)
    table = PricingTable.get_table_by_product(product)
    table_json = json.dumps(table, cls=LazyEncoder)
    translation.deactivate()
    response = HttpResponse(table_json, content_type='application/json')
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response["Access-Control-Max-Age"] = "1000"
    response["Access-Control-Allow-Headers"] = "*"
    return response
