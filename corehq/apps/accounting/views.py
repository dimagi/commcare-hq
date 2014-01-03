from django.http import HttpResponseRedirect
from django.shortcuts import render
from corehq import AccountingInterface
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
    parent_link = '<a href="%s">%s<a>' % (AccountingInterface.get_url(), AccountingInterface.name)
    return render(request,
                  'manage_account.html',
                  dict(account_name=BillingAccount.objects.get(id=account_id).name,
                       parent_link=parent_link))
