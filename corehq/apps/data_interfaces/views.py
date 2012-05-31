from corehq.apps.reports.views import datespan_default
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from dimagi.utils.modules import to_function
from dimagi.utils.web import render_to_response
from corehq.apps.domain.decorators import login_and_domain_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseNotFound, Http404, HttpResponseRedirect
from django.conf import settings

require_can_edit_data = require_permission(Permissions.edit_data)

@require_can_edit_data
def default(request, domain, template="data_interfaces/data_interfaces_base.html"):
#    context = {
#        'domain': domain,
#        'slug': None,
#        'report': {'name': "Select a Data Interface to View"}
#    }
#    return render_to_response(request, template, context)
    return HttpResponseRedirect(reverse('data_interface_dispatcher', args=[domain, 'reassign_cases']))

@require_can_edit_data
@datespan_default
def report_dispatcher(request, domain, slug, return_json=False, map='DATA_INTERFACE_MAP', export=False, custom=False):
    mapping = getattr(settings, map, None)
    if not mapping or (custom and not domain in mapping):
        return HttpResponseNotFound("Sorry, no reports have been configured yet.")
    if custom:
        mapping = mapping[domain]
    for key, models in mapping.items():
        for model in models:
            klass = to_function(model)
            if klass.slug == slug:
                k = klass(domain, request)
                if not request.couch_user.can_edit_data(domain):
                    raise Http404
                elif return_json:
                    return k.as_json()
                elif export:
                    return k.as_export()
                else:
                    return k.as_view()
    raise Http404