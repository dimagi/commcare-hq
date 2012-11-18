from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from corehq.apps.domain.decorators import require_superuser
from django.views.decorators.http import require_POST
from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.management.commands import bootstrap_psi
import json

@require_superuser
@require_POST
def bootstrap(request, domain):
    D = Domain.get_by_name(domain)
    if D.commtrack_enabled:
        response = {'status': 'already configured'}
    else:
        bootstrap_psi.one_time_setup(D)
        response = {'status': 'set up successfully'}

    return HttpResponse(json.dumps(response), 'text/json')
