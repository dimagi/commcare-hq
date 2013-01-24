from django.http import HttpResponse, HttpResponseRedirect, Http404
from corehq.apps.domain.decorators import require_superuser, domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from django.core.urlresolvers import reverse
from dimagi.utils.web import render_to_response, get_url_base
from django.contrib import messages
import json
from couchdbkit import ResourceNotFound

@domain_admin_required # TODO: will probably want less restrictive permission
def locations_list(request, domain):
    context = {
        'domain': domain,
        'api_root': reverse('api_dispatch_list', kwargs={'domain': domain,
                                                         'resource_name': 'location', 
                                                         'api_name': 'v0.3'})
    }
    return render_to_response(request, 'locations/manage/locations.html', context)
