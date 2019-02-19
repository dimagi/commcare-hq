from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError


@require_deploy_apps
def multimedia_ajax(request, domain, app_id):
    app = get_app(domain, app_id)
    if app.get_doc_type() == 'Application':
        try:
            multimedia_state = app.check_media_state()
        except ReportConfigurationNotFoundError:
            return JsonResponse(
                {"message": _("One of the Report menus is misconfigured, please try again after they are fixed")},
                status=500)
        context = {
            'multimedia_state': multimedia_state,
            'domain': domain,
            'app': app,
        }
        return render(request, "app_manager/partials/settings/multimedia_ajax.html", context)
    else:
        raise Http404()
