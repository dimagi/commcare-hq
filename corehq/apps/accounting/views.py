import datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import TemplateView
from corehq import AccountingInterface, SubscriptionInterface
from corehq.apps.accounting.forms import *
from corehq.apps.accounting.models import *
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.users.models import WebUser


@require_superuser
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


class NewBillingAccountView(TemplateView):
    template_name = 'manage_account.html'
    name = 'new_billing_account'

    def get_context_data(self):
        return dict(form=BillingAccountForm(None),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name),
                    )

    def post(self, request, *args, **kwargs):
        # TODO validate data
        name = self.request.POST['name']
        salesforce_account_id = self.request.POST['salesforce_account_id']
        currency, _ = Currency.objects.get_or_create(code=self.request.POST['currency'])
        account = BillingAccount(name=name,
                                 salesforce_account_id=salesforce_account_id,
                                 currency=currency)
        account.save()
        return HttpResponseRedirect(reverse('manage_billing_account', args=(account.id,)))


def adjust_credit(request, account_id=None, subscription_id=None):
    credit_form = CreditForm(account_id or subscription_id, account_id is not None, request.POST)
    credit_form.is_valid()
    if account_id is not None:
        account = BillingAccount.objects.get(id=account_id)
        credit_line_kwargs = dict(account=account,
                                  subscription=None)
    elif subscription_id is not None:
        subscription = Subscription.objects.get(id=subscription_id)
        credit_line_kwargs = dict(account=subscription.account,
                                  subscription=subscription)
    else:
        raise ValidationError('invalid credit adjustment')
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
class ManageBillingAccountView(TemplateView):
    template_name = 'manage_account.html'
    name = 'manage_billing_account'

    def get_context_data(self):
        account = BillingAccount.objects.get(id=self.args[0])
        return dict(account=account,
                    credit_form=CreditForm(account.id, True),
                    credit_list=CreditLine.objects.filter(account=account),
                    form=BillingAccountForm(account),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name),
                    subscription_list=[(sub,
                                        Invoice.objects.filter(subscription=sub).latest('date_due').date_due # TODO - check query
                                            if len(Invoice.objects.filter(subscription=sub)) != 0 else 'None on record',
                                        )
                                       for sub in Subscription.objects.filter(account=account)],
                    )

    def post(self, request, *args, **kwargs):
        # TODO validate data
        if 'set_subscription' in self.request.POST:
            account = BillingAccount.objects.get(id=self.args[0])
            account.name = self.request.POST['name']
            account.salesforce_account_id = self.request.POST['salesforce_account_id']
            account.currency, _ = Currency.objects.get_or_create(code=self.request.POST['currency'])
            for web_user_email in self.request.POST['billing_account_admins'].split(','):
                if WebUser.get_by_username(web_user_email.strip()) is not None:
                    admin, _ = BillingAccountAdmin.objects.get_or_create(web_user=web_user_email)
                    account.billing_admins.add(admin)
            account.save()

            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            contact_info.first_name = self.request.POST['first_name']
            contact_info.last_name = self.request.POST['last_name']
            contact_info.company_name = self.request.POST['company_name']
            contact_info.phone_number = self.request.POST['phone_number']
            contact_info.first_line = self.request.POST['address_line_1']
            contact_info.second_line = self.request.POST['address_line_2']
            contact_info.city = self.request.POST['city']
            contact_info.state_province_region = self.request.POST['region']
            contact_info.postal_code = self.request.POST['postal_code']
            contact_info.country = self.request.POST['country']
            contact_info.save()
        elif 'adjust_credit' in self.request.POST:
            adjust_credit(request, account_id=self.args[0])

        return self.get(request, *args, **kwargs)


def datestring_to_date(datestring):
    if datestring is None or datestring == '':
        return None
    return datetime.date(*tuple([int(i) for i in datestring.split('-')]))


class NewSubscriptionView(TemplateView):
    template_name = 'edit_subscription.html'
    name = 'new_subscription'

    def get_context_data(self):
        return dict(form=SubscriptionForm(None),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name))

    def post(self, request, *args, **kwargs):
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
                                    salesforce_contract_id=account.salesforce_account_id,
                                    subscriber=Subscriber.objects.get_or_create(domain=domain,
                                                                                organization=None)[0])
        subscription.save()
        return HttpResponseRedirect(reverse(ManageBillingAccountView.name, args=(account_id,)))


class EditSubscriptionView(TemplateView):
    template_name = 'edit_subscription.html'
    name = 'edit_subscription'

    def get_context_data(self):
        subscription = Subscription.objects.get(id=self.args[0])
        return dict(cancel_form=CancelForm(),
                    credit_form=CreditForm(subscription.id, False),
                    credit_list=CreditLine.objects.filter(subscription=subscription),
                    form=SubscriptionForm(subscription),
                    parent_link='<a href="%s">%s<a>' % (SubscriptionInterface.get_url(), SubscriptionInterface.name),
                    subscription=subscription
                    )

    def post(self, request, *args, **kwargs):
        # TODO validate data
        if 'set_subscription' in self.request.POST:
            self.set_subscription()
        elif 'adjust_credit' in self.request.POST:
            adjust_credit(request, subscription_id=self.args[0])
        elif 'cancel_subscription' in self.request.POST:
            self.cancel_subscription()
        return self.get(request, *args, **kwargs)

    def set_subscription(self):
        #TODO - allow user to remove dates that haven't already passed
        subscription = Subscription.objects.get(id=self.args[0])
        subscription.date_start = \
            datestring_to_date(self.request.POST.get('start_date')) or subscription.date_start
        subscription.date_end = \
            datestring_to_date(self.request.POST.get('end_date')) or subscription.date_end
        subscription.date_delay_invoicing = \
            datestring_to_date(self.request.POST.get('delay_invoice_until')) or subscription.date_delay_invoicing
        subscription.save()

    def cancel_subscription(self):
        subscription = Subscription.objects.get(id=self.args[0])
        if subscription.date_start > datetime.date.today():
            subscription.date_start = datetime.date.today()
        subscription.date_end = datetime.date.today()
        subscription.is_active = False
        subscription.save()
