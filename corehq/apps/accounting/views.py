from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import TemplateView
from corehq import AccountingInterface
from corehq.apps.accounting.forms import BillingAccountForm
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.domain.decorators import require_superuser


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


# make sure to require superuser
class ManageBillingAccountView(TemplateView):
    template_name = 'manage_account.html'

    def get_context_data(self):
        account = BillingAccount.objects.get(id=2)
        return dict(account=account,
                    form=BillingAccountForm(account),
                    parent_link='<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name),
                    )
