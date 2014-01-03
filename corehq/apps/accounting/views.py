from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from corehq import AccountingInterface2
from corehq.apps.accounting.models import BillingAccount, Currency
from corehq.apps.domain.decorators import require_superuser


@require_superuser
def view_billing_accounts(request):
    return render(request, "view_billing_accounts.html",
                  {'account_list': BillingAccount.objects.filter(),
                   })

@require_superuser
def accounting_default(request):
    return HttpResponseRedirect(AccountingInterface2.get_url())