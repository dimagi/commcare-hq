from corehq import AccountingInterface, SubscriptionInterface
from corehq.apps.accounting.forms import *
from corehq.apps.accounting.models import *
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BaseSectionPageView
from dimagi.utils.decorators.memoized import memoized
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator


@require_superuser
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


class AccountingSectionView(BaseSectionPageView):
    section_name = 'Accounting'

    @property
    def section_url(self):
        return reverse('accounting_default')

    @method_decorator(require_superuser)
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
        context = super(NewBillingAccountView, self).main_context
        context.update({'form': self.account_form})
        return context

    @property
    def page_title(self):
        return "New Billing Account"

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        if self.account_form.is_valid():
            account = self.account_form.create_account()
            return HttpResponseRedirect(reverse('manage_billing_account', args=(account.id,)))
        else:
            return self.get(request, *args, **kwargs)


def adjust_credit(credit_form, account=None, subscription=None):
    amount = credit_form.cleaned_data['amount']
    note = credit_form.cleaned_data['note']
    def get_account_for_rate():
        return account if account is not None else subscription.account
    if credit_form.cleaned_data['rate_type'] == 'Product':
        CreditLine.add_rate_credit(amount, get_account_for_rate(),
                                   product_rate=SoftwareProductRate.objects.get(id=credit_form.cleaned_data['product']),
                                   subscription=subscription,
                                   note=note)
    elif credit_form.cleaned_data['rate_type'] == 'Feature':
        CreditLine.add_rate_credit(amount, get_account_for_rate(),
                                   feature_rate=FeatureRate.objects.get(id=credit_form.cleaned_data['feature']),
                                   subscription=subscription,
                                   note=note)
    elif account is not None:
        CreditLine.add_account_credit(amount, account,
                                      note=note)
    elif subscription is not None:
        CreditLine.add_subscription_credit(amount, subscription,
                                           note=note)
    else:
        raise ValueError('invalid credit adjustment')


class ManageBillingAccountView(BillingAccountsSectionView):
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

    def data(self):
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
    def page_context(self):
        context = super(ManageBillingAccountView, self).main_context
        context.update(self.data())
        return context

    @property
    def page_title(self):
        return "Manage Billing Account"

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.args[0],))

    def post(self, request, *args, **kwargs):
        if 'account' in self.request.POST and self.account_form.is_valid():
            self.account_form.update_account_and_contacts(self.account)
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            adjust_credit(self.credit_form, account=self.account)

        return self.get(request, *args, **kwargs)


class NewSubscriptionView(AccountingSectionView):
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
        context = super(NewSubscriptionView, self).main_context
        context.update(dict(form=self.subscription_form))
        return context

    @property
    def page_title(self):
        return 'New Subscription'

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

    def data(self):
        return {'cancel_form': CancelForm(),
                'credit_form': self.get_appropriate_credit_form(self.subscription),
                'credit_list': CreditLine.objects.filter(subscription=self.subscription),
                'form': self.get_appropriate_subscription_form(self.subscription),
                'parent_link': '<a href="%s">%s<a>' % (SubscriptionInterface.get_url(), SubscriptionInterface.name),
                'subscription': self.subscription,
                'subscription_canceled': self.subscription_canceled if hasattr(self, 'subscription_canceled') else False
                }

    @property
    def page_context(self):
        context = super(EditSubscriptionView, self).main_context
        context.update(self.data())
        return context

    @property
    def page_title(self):
        return 'Edit Subscription'

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
            adjust_credit(self.credit_form, subscription=self.subscription)
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
