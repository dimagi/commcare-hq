from corehq.apps.reports.views import datespan_default
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from dimagi.utils.modules import to_function
from dimagi.utils.web import render_to_response
from corehq.apps.domain.decorators import login_and_domain_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseNotFound, Http404, HttpResponseRedirect
from django.conf import settings
from corehq.apps.reports.dispatcher import ReportDispatcher

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

#@require_can_edit_data
#@datespan_default
#def report_dispatcher(request, domain, slug, return_json=False,
#                      map='DATA_INTERFACE_MAP', export=False, custom=False,
#                      async=False, async_filters=False, static_only=False):
#
#    def permissions_check(couch_user, domain, model):
#        return couch_user.can_edit_data(domain)
#
#    mapping = getattr(settings, map, None)
#    dispatcher = ReportDispatcher(mapping, permissions_check)
#    return dispatcher.dispatch(request, domain, slug, return_json, export,
#                               custom, async, async_filters)
#
