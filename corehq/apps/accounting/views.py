import datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import TemplateView
from corehq import AccountingInterface, SubscriptionInterface
from corehq.apps.accounting.forms import BillingAccountForm, SubscriptionForm
from corehq.apps.accounting.models import BillingAccount, Currency, Subscription, SoftwarePlanVersion, Subscriber, BillingContactInfo
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.users.models import WebUser


@require_superuser
def view_billing_accounts(request):
    return render(request, "view_billing_accounts.html",
                  {'account_list': BillingAccount.objects.filter(),
                   })


@require_superuser
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface.get_url())


@require_superuser
def manage_billing_account(request, account_id):
    template = 'manage_account.html'
    account = BillingAccount.objects.get(id=account_id)
    parent_link = '<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name)
    return render(request,
                  template,
                  dict(account=account,
                       form=BillingAccountForm(account),
                       parent_link=parent_link))


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
                    form=BillingAccountForm(account),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name),
                    subscription_list=Subscription.objects.filter(account=account),
                    )

    def post(self, request, *args, **kwargs):
        # TODO validate data
        account = BillingAccount.objects.get(id=self.args[0])
        account.name = self.request.POST['name']
        account.salesforce_account_id = self.request.POST['salesforce_account_id']
        account.currency, _ = Currency.objects.get_or_create(code=self.request.POST['currency'])
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

        return self.get(request, *args, **kwargs)


class NewSubscriptionView(TemplateView):
    template_name = 'new_subscription.html'
    name = 'new_subscription'

    def get_context_data(self):
        return dict(form=SubscriptionForm(None),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name))

    def post(self, request, *args, **kwargs):
        account_id = self.args[0]
        date_start = datetime.datetime(int(self.request.POST['start_date_year']),
                                       int(self.request.POST['start_date_month']),
                                       int(self.request.POST['start_date_day']))
        date_end = datetime.datetime(int(self.request.POST['end_date_year']),
                                     int(self.request.POST['end_date_month']),
                                     int(self.request.POST['end_date_day']))
        date_delay_invoicing = datetime.datetime(int(self.request.POST['delay_invoice_until_year']),
                                                 int(self.request.POST['delay_invoice_until_month']),
                                                 int(self.request.POST['delay_invoice_until_day']))
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
        return dict(form=SubscriptionForm(subscription),
                    parent_link='<a href="%s">%s<a>' % (SubscriptionInterface.get_url(), SubscriptionInterface.name),
                    )

    def post(self, request, *args, **kwargs):
        # TODO validate data
        subscription = Subscription.objects.get(id=self.args[0])
        subscription.date_start = datetime.datetime(int(self.request.POST['start_date_year']),
                                                    int(self.request.POST['start_date_month']),
                                                    int(self.request.POST['start_date_day']))
        subscription.date_end = datetime.datetime(int(self.request.POST['end_date_year']),
                                                  int(self.request.POST['end_date_month']),
                                                  int(self.request.POST['end_date_day']))
        subscription.date_delay_invoicing = datetime.datetime(int(self.request.POST['delay_invoice_until_year']),
                                                              int(self.request.POST['delay_invoice_until_month']),
                                                              int(self.request.POST['delay_invoice_until_day']))
        subscription.save()
        return self.get(request, *args, **kwargs)
