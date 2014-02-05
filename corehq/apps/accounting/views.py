import json
import datetime

from django.conf import settings
from django.utils import translation
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator

from dimagi.utils.decorators.memoized import memoized

from corehq.apps.accounting.forms import (BillingAccountForm, CreditForm, SubscriptionForm, CancelForm,
                                          PlanInformationForm, SoftwarePlanVersionForm, FeatureRateForm,
                                          ProductRateForm, RoleForm)
from corehq.apps.accounting.interface import AccountingInterface, SubscriptionInterface, SoftwarePlanInterface
from corehq.apps.accounting.models import (SoftwareProductType, Invoice, BillingAccount, CreditLine, Subscription,
                                           SoftwarePlanVersion, SoftwarePlan)
from corehq.apps.accounting.async_handlers import (FeatureRateAsyncHandler, Select2RateAsyncHandler,
                                                   SoftwareProductRateAsyncHandler, RoleAsyncHandler)
from corehq.apps.accounting.user_text import PricingTable
from corehq.apps.accounting.utils import LazyEncoder
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq import toggles
from toggle.decorators import require_toggle


@require_superuser
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


class AccountingSectionView(BaseSectionPageView):
    section_name = 'Accounting'

    @property
    def section_url(self):
        return reverse('accounting_default')

    @method_decorator(require_toggle(toggles.ACCOUNTING_PREVIEW))
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


class ManageBillingAccountView(BillingAccountsSectionView):
    page_title = 'Manage Billing Account'
    template_name = 'accounting/accounts.html'
    urlname = 'manage_billing_account'

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
        if 'account' in self.request.POST and self.account_form.is_valid():
            self.account_form.update_account_and_contacts(self.account)
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            self.credit_form.adjust_credit(account=self.account)

        return self.get(request, *args, **kwargs)


class NewSubscriptionView(AccountingSectionView):
    page_title = 'New Subscription'
    template_name = 'accounting/subscriptions_base.html'
    urlname = 'new_subscription'

    @property
    @memoized
    def subscription_form(self):
        if self.request.method == 'POST':
            return SubscriptionForm(None, self.request.POST)
        return SubscriptionForm(None)

    @property
    def page_context(self):
        return {
            'form': self.subscription_form,
        }

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.args[0],))

    @property
    def parent_pages(self):
        return [{
            'title': AccountingInterface.name,
            'url': AccountingInterface.get_url(),
        }]

    def post(self, request, *args, **kwargs):
        if self.subscription_form.is_valid():
            account_id = self.args[0]
            self.subscription_form.create_subscription(account_id)
            return HttpResponseRedirect(reverse(ManageBillingAccountView.urlname, args=(account_id,)))
        return self.get(request, *args, **kwargs)


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
            return SubscriptionForm(self.subscription, self.request.POST)
        return SubscriptionForm(self.subscription)

    def get_appropriate_subscription_form(self, subscription):
        if (not self.subscription_form.is_bound) or (not self.subscription_form.is_valid()):
            return self.subscription_form
        return SubscriptionForm(subscription)

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
            self.subscription_form.update_subscription(self.subscription)
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            self.credit_form.adjust_credit(subscription=self.subscription)
        elif 'cancel_subscription' in self.request.POST:
            self.cancel_subscription()
        return self.get(request, *args, **kwargs)

    def cancel_subscription(self):
        if self.subscription.date_start > datetime.date.today():
            self.subscription.date_start = datetime.date.today()
        self.subscription.date_end = datetime.date.today()
        self.subscription.is_active = False
        self.subscription.save()
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


class EditSoftwarePlanView(AccountingSectionView):
    template_name = 'accounting/plans.html'
    urlname = 'edit_software_plan'
    page_title = "Edit Software Plan"
    async_handlers = [
        Select2RateAsyncHandler,
        FeatureRateAsyncHandler,
        SoftwareProductRateAsyncHandler,
        RoleAsyncHandler,
    ]

    @property
    @memoized
    def plan(self):
        return SoftwarePlan.objects.get(id=self.args[0])

    @property
    @memoized
    def plan_info_form(self):
        if self.request.method == 'POST':
            return PlanInformationForm(self.plan, self.request.POST)
        return PlanInformationForm(self.plan)

    @property
    @memoized
    def software_plan_version_form(self):
        if self.request.method == 'POST':
            return SoftwarePlanVersionForm(self.plan, self.plan.get_version(), self.request.POST)
        return SoftwarePlanVersionForm(self.plan, self.plan.get_version())

    @property
    def page_context(self):
        return {
            'plan_info_form': self.plan_info_form,
            'plan_version_form': self.software_plan_version_form,
            'feature_rate_form': FeatureRateForm(),
            'product_rate_form': ProductRateForm(),
            'role_form': RoleForm(),
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

    @property
    def handler_slug(self):
        return self.request.POST.get('handler')

    def get_async_handler(self):
        handler_class = dict([(h.slug, h) for h in self.async_handlers])[self.handler_slug]
        return handler_class(self.request)

    def post(self, request, *args, **kwargs):
        if self.handler_slug in [h.slug for h in self.async_handlers]:
            return self.get_async_handler().get_response()
        if 'update_version' in request.POST:
            if self.software_plan_version_form.is_valid():
                self.software_plan_version_form.save(request)
                return HttpResponseRedirect(self.page_url)
        elif self.plan_info_form.is_valid():
            self.plan_info_form.update_plan(self.plan)
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
    return HttpResponse(table_json, content_type='application/json')
