from django.http import HttpResponse
from corehq.apps.domain.decorators import require_superuser


@require_superuser
def view_billing_accounts(request):
    return HttpResponse()
