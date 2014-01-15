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


# TODO make sure to require superuser
class ManageBillingAccountView(TemplateView):
    template_name = 'manage_account.html'
    name = 'manage_billing_account'

    def get_context_data(self):
        account = BillingAccount.objects.get(id=self.args[0])
        return dict(account=account,
                    credit_form=CreditForm(account.id, True),
                    credit_list=None,
                    form=BillingAccountForm(account),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name),
                    subscription_list=[(sub,
                                        Invoice.objects.filter(subscription=sub).latest('date_due').date_due # TODO - check query
                                            if len(Invoice.objects.filter(subscription=sub)) != 0 else 'None on record',
                                        'ADD LINE ITEMS')
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
            account = BillingAccount.objects.get(id=self.args[0])
            credit_line = CreditLine.objects.get_or_create(account=account)
            credit_line.adjust_credit_balance(self.request.POST['amount'],
                                              note=self.request.POST['note'],
                                              )

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
        date_start = datestring_to_date(self.request.POST.get('start_date'))
        date_end = datestring_to_date(self.request.POST.get('end_date'))
        date_delay_invoicing = datestring_to_date(self.request.POST.get('delay_invoice_until'))
        subscription = Subscription(account=BillingAccount.objects.get(id=account_id),
                                    date_start=date_start,
                                    date_end=date_end,
                                    date_delay_invoicing=date_delay_invoicing,
                                    plan=SoftwarePlanVersion.objects.all()[0],# TODO set
                                    subscriber=Subscriber.objects.all()[0])# TODO set
        subscription.save()
        return HttpResponseRedirect(reverse(ManageBillingAccountView.name, args=(account_id,)))


class EditSubscriptionView(TemplateView):
    template_name = 'edit_subscription.html'
    name = 'edit_subscription'

    def get_context_data(self):
        subscription = Subscription.objects.get(id=self.args[0])
        return dict(cancel_form=CancelForm(),
                    credit_form=CreditForm(subscription.id, False),
                    credit_list=None,
                    form=SubscriptionForm(subscription),
                    parent_link='<a href="%s">%s<a>' % (SubscriptionInterface.get_url(), SubscriptionInterface.name),
                    subscription=subscription
                    )

    def post(self, request, *args, **kwargs):
        # TODO validate data
        if 'set_subscription' in self.request.POST:
            subscription = Subscription.objects.get(id=self.args[0])
            subscription.date_start = \
                datestring_to_date(self.request.POST.get('start_date')) or subscription.date_start
            subscription.date_end = \
                datestring_to_date(self.request.POST.get('end_date')) or subscription.date_end
            subscription.date_delay_invoicing = \
                datestring_to_date(self.request.POST.get('delay_invoice_until')) or subscription.date_delay_invoicing
            subscription.save()
        elif 'adjust_credit' in self.request.POST:
            print 'submitted credit adjustment'
        elif 'cancel_subscription' in self.request.POST:
            print 'canceling'
        return self.get(request, *args, **kwargs)
