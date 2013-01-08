from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect

require_can_edit_data = require_permission(Permissions.edit_data)

@require_can_edit_data
def default(request, domain):
#    context = {
#        'domain': domain,
#        'slug': None,
#        'report': {'name': "Select a Data Interface to View"}
#    }
#    return render_to_response(request, template, context)
    from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
    return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(), args=[domain, 'reassign_cases']))
