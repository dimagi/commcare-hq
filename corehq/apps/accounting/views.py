import datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import TemplateView
from corehq import AccountingInterface, SubscriptionInterface
from corehq.apps.accounting.forms import *
from corehq.apps.accounting.models import *
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.hqwebapp.views import BaseSectionPageView
from corehq.apps.users.models import WebUser
from dimagi.utils.decorators.memoized import memoized


@require_superuser
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


class AccountingSectionView(BaseSectionPageView):
    section_name = 'Accounting'
    name = ''

    @property
    def section_url(self):
        return reverse('accounting_default')

    @property
    def page_context(self):
        return {}


class BillingAccountsSectionView(AccountingSectionView):
    template_name = 'accounting/accounts.html'

    @property
    def parent_pages(self):
        return [{
            'title': AccountingInterface.name,
            'url': AccountingInterface.get_url(),
        }]


class SubscriptionSectionView(AccountingSectionView):
    template_name = 'accounting/subscriptions.html'

    @property
    def parent_pages(self):
        return [{
            'title': SubscriptionInterface.name,
            'url': SubscriptionInterface.get_url(),
        }]


class NewBillingAccountView(BillingAccountsSectionView):
    name = 'new_billing_account'

    @property
    @memoized
    def account_form(self):
        if self.request.method == 'POST':
            return BillingAccountForm(None, self.request.POST)
        return BillingAccountForm(None)

    @property
    def main_context(self):
        context = super(NewBillingAccountView, self).main_context
        context.update(dict(form=self.account_form))
        return context

    @property
    def page_name(self):
        return 'New Billing Account'

    @property
    def page_url(self):
        return reverse(self.name)

    def post(self, request, *args, **kwargs):
        if self.account_form.is_valid():
            name = self.account_form.cleaned_data['name']
            salesforce_account_id = self.account_form.cleaned_data['salesforce_account_id']
            currency, _ = Currency.objects.get_or_create(code=self.account_form.cleaned_data['currency'])
            account = BillingAccount(name=name,
                                     salesforce_account_id=salesforce_account_id,
                                     currency=currency)
            account.save()
            return HttpResponseRedirect(reverse('manage_billing_account', args=(account.id,)))
        else:
            return self.get(request, *args, **kwargs)


def adjust_credit(credit_form, account_id=None, subscription_id=None):
    if account_id is not None:
        account = BillingAccount.objects.get(id=account_id)
        credit_line_kwargs = dict(account=account,
                                  subscription=None)
    elif subscription_id is not None:
        subscription = Subscription.objects.get(id=subscription_id)
        credit_line_kwargs = dict(account=subscription.account,
                                  subscription=subscription)
    else:
        raise ValueError('invalid credit adjustment')
    if credit_form.cleaned_data['rate_type'] == 'Product':
        credit_line_kwargs.update(
            product_rate=SoftwareProductRate.objects.get(id=credit_form.cleaned_data['product']))
    elif credit_form.cleaned_data['rate_type'] == 'Feature':
        credit_line_kwargs.update(
            feature_rate=FeatureRate.objects.get(id=credit_form.cleaned_data['feature']))
    else:
        credit_line_kwargs.update(feature_rate=None,
                                  product_rate=None)
    credit_line, _ = CreditLine.objects.get_or_create(**credit_line_kwargs)
    credit_line.adjust_credit_balance(credit_form.cleaned_data['amount'],
                                      note=credit_form.cleaned_data['note'],
                                      )


# TODO make sure to require superuser
class ManageBillingAccountView(BillingAccountsSectionView):
    name = 'manage_billing_account'

    @property
    @memoized
    def account_form(self):
        account = BillingAccount.objects.get(id=self.args[0])
        if self.request.method == 'POST' and 'account' in self.request.POST:
            return BillingAccountForm(account, self.request.POST)
        return BillingAccountForm(account)

    @property
    @memoized
    def credit_form(self):
        account = BillingAccount.objects.get(id=self.args[0])
        if self.request.method == 'POST' and 'adjust_credit' in self.request.POST:
            return CreditForm(account.id, True, self.request.POST)
        return CreditForm(account.id, True)

    def get_appropriate_credit_form(self, account):
        if (not self.credit_form.is_bound) or (not self.credit_form.is_valid()):
            return self.credit_form
        return CreditForm(account.id, True)

    def data(self):
        account = BillingAccount.objects.get(id=self.args[0])
        return dict(account=account,
                    credit_form=self.get_appropriate_credit_form(account),
                    credit_list=CreditLine.objects.filter(account=account),
                    form=self.account_form,
                    subscription_list=[(sub,
                                        Invoice.objects.filter(subscription=sub).latest('date_due').date_due # TODO - check query
                                            if len(Invoice.objects.filter(subscription=sub)) != 0 else 'None on record',
                                        )
                                       for sub in Subscription.objects.filter(account=account)],
                    )

    @property
    def main_context(self):
        context = super(ManageBillingAccountView, self).main_context
        context.update(self.data())
        return context

    @property
    def page_name(self):
        return 'Manage Billing Account'

    @property
    def page_url(self):
        return reverse(self.name, args=(self.args[0],))

    def post(self, request, *args, **kwargs):
        if 'account' in self.request.POST and self.account_form.is_valid():
            account = BillingAccount.objects.get(id=self.args[0])
            account.name = self.account_form.cleaned_data['name']
            account.salesforce_account_id = self.account_form.cleaned_data['salesforce_account_id']
            account.currency, _ = Currency.objects.get_or_create(code=self.request.POST['currency'])
            for web_user_email in self.account_form.cleaned_data['billing_account_admins'].split(','):
                if WebUser.get_by_username(web_user_email.strip()) is not None:
                    admin, _ = BillingAccountAdmin.objects.get_or_create(web_user=web_user_email)
                    account.billing_admins.add(admin)
            account.save()

            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            contact_info.first_name = self.account_form.cleaned_data['first_name']
            contact_info.last_name = self.account_form.cleaned_data['last_name']
            contact_info.company_name = self.account_form.cleaned_data['company_name']
            contact_info.phone_number = self.account_form.cleaned_data['phone_number']
            contact_info.first_line = self.account_form.cleaned_data['address_line_1']
            contact_info.second_line = self.account_form.cleaned_data['address_line_2']
            contact_info.city = self.account_form.cleaned_data['city']
            contact_info.state_province_region = self.account_form.cleaned_data['region']
            contact_info.postal_code = self.account_form.cleaned_data['postal_code']
            contact_info.country = self.account_form.cleaned_data['country']
            contact_info.save()
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            adjust_credit(self.credit_form, account_id=self.args[0])

        return self.get(request, *args, **kwargs)


class NewSubscriptionView(SubscriptionSectionView):
    name = 'new_subscription'

    @property
    @memoized
    def subscription_form(self):
        if self.request.method == 'POST':
            return SubscriptionForm(None, self.request.POST)
        return SubscriptionForm(None)

    @property
    def main_context(self):
        context = super(NewSubscriptionView, self).main_context
        context.update(dict(form=self.subscription_form))
        return context

    @property
    def page_name(self):
        return 'New Subscription'

    @property
    def page_url(self):
        return reverse(self.name, args=(self.args[0],))

    def post(self, request, *args, **kwargs):
        if self.subscription_form.is_valid():
            account_id = self.args[0]
            account = BillingAccount.objects.get(id=account_id)
            subscription_form = SubscriptionForm(None, request.POST)
            subscription_form.is_valid()
            date_start = subscription_form.cleaned_data['start_date']
            date_end = subscription_form.cleaned_data['end_date']
            date_delay_invoicing = subscription_form.cleaned_data['delay_invoice_until']
            plan_id = subscription_form.cleaned_data['plan']
            domain = subscription_form.cleaned_data['domain']
            subscription = Subscription(account=account,
                                        date_start=date_start,
                                        date_end=date_end,
                                        date_delay_invoicing=date_delay_invoicing,
                                        plan=SoftwarePlanVersion.objects.get(id=plan_id),
                                        salesforce_contract_id=subscription_form.cleaned_data['salesforce_contract_id'],
                                        subscriber=Subscriber.objects.get_or_create(domain=domain,
                                                                                    organization=None)[0])
            subscription.save()
            return HttpResponseRedirect(reverse(ManageBillingAccountView.name, args=(account_id,)))
        return self.get(request, *args, **kwargs)


class EditSubscriptionView(SubscriptionSectionView):
    name = 'edit_subscription'

    @property
    @memoized
    def subscription_form(self):
        subscription = Subscription.objects.get(id=self.args[0])
        if self.request.method == 'POST' and 'set_subscription' in self.request.POST:
            return SubscriptionForm(subscription, self.request.POST)
        return SubscriptionForm(subscription)

    def get_appropriate_subscription_form(self, subscription):
        if (not self.subscription_form.is_bound) or (not self.subscription_form.is_valid()):
            return self.subscription_form
        return SubscriptionForm(subscription)

    @property
    @memoized
    def credit_form(self):
        subscription = Subscription.objects.get(id=self.args[0])
        if self.request.method == 'POST' and 'adjust_credit' in self.request.POST:
            return CreditForm(subscription.id, False, self.request.POST)
        return CreditForm(subscription.id, False)

    def get_appropriate_credit_form(self, subscription):
        if (not self.credit_form.is_bound) or (not self.credit_form.is_valid()):
            return self.credit_form
        return CreditForm(subscription.id, False)

    def data(self):
        subscription = Subscription.objects.get(id=self.args[0])
        return dict(cancel_form=CancelForm(),
                    credit_form=self.get_appropriate_credit_form(subscription),
                    credit_list=CreditLine.objects.filter(subscription=subscription),
                    form=self.get_appropriate_subscription_form(subscription),
                    parent_link='<a href="%s">%s<a>' % (SubscriptionInterface.get_url(), SubscriptionInterface.name),
                    subscription=subscription,
                    subscription_canceled=self.subscription_canceled if hasattr(self, 'subscription_canceled') else False
                    )

    @property
    def main_context(self):
        context = super(EditSubscriptionView, self).main_context
        context.update(self.data())
        return context

    @property
    def page_name(self):
        return 'Edit Subscription'

    @property
    def page_url(self):
        return reverse(self.name, args=(self.args[0],))

    def post(self, request, *args, **kwargs):
        if 'set_subscription' in self.request.POST and self.subscription_form.is_valid():
            self.set_subscription()
        elif 'adjust_credit' in self.request.POST and self.credit_form.is_valid():
            adjust_credit(self.credit_form, subscription_id=self.args[0])
        elif 'cancel_subscription' in self.request.POST:
            self.cancel_subscription()
        return self.get(request, *args, **kwargs)

    def set_subscription(self):
        subscription = Subscription.objects.get(id=self.args[0])
        if self.subscription_form.fields['start_date'].required:
            subscription.date_start = self.subscription_form.cleaned_data['start_date']
        if subscription.date_end is None or subscription.date_end > datetime.date.today():
            subscription.date_end = self.subscription_form.cleaned_data['end_date']
        if subscription.date_delay_invoicing is None \
            or subscription.date_delay_invoicing > datetime.date.today():
            subscription.date_delay_invoicing = self.subscription_form.cleaned_data['delay_invoice_until']
        subscription.save()

    def cancel_subscription(self):
        subscription = Subscription.objects.get(id=self.args[0])
        if subscription.date_start > datetime.date.today():
            subscription.date_start = datetime.date.today()
        subscription.date_end = datetime.date.today()
        subscription.is_active = False
        subscription.save()
        self.subscription_canceled = True
