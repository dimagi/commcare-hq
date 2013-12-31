from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from corehq.apps.domain.decorators import require_superuser


@require_superuser
def view_billing_accounts(request):
    return render(request, "list_backends.html", {})
