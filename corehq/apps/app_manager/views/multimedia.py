from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.template.defaultfilters import filesizeformat
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.dbaccessors import get_app, get_apps_in_domain
from corehq.apps.app_manager.decorators import require_deploy_apps
from corehq.apps.app_manager.util import is_linked_app, is_remote_app
from corehq.apps.app_manager.views.utils import (
    get_multimedia_sizes_for_build,
    get_new_multimedia_between_builds,
)
from corehq.apps.userreports.exceptions import ReportConfigurationNotFoundError
from corehq import toggles
from corehq.util.quickcache import quickcache


@require_deploy_apps
def multimedia_ajax(request, domain, app_id):
    app = get_app(domain, app_id)
    if not is_remote_app(app):
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
            'is_linked_app': is_linked_app(app),
        }

        return render(request, "app_manager/partials/settings/multimedia_ajax.html", context)
    else:
        raise Http404()


def _update_mm_sizes(mm_sizes):
    mm_sizes['Total'] = sum(mm_sizes.values())
    mm_sizes = {
        mm_type: filesizeformat(mm_size)
        for mm_type, mm_size in
        mm_sizes.items()
    }
    return mm_sizes


@require_deploy_apps
@quickcache(['domain', 'app_id', 'build_profile_id'], timeout=60 * 60)
def get_multimedia_sizes(request, domain, app_id, build_profile_id=None):
    """
    return size for different multimedia types and total for an app, directly presentable to the user
    """
    mm_sizes = get_multimedia_sizes_for_build(domain, build_id=app_id, build_profile_id=build_profile_id)
    if mm_sizes:
        mm_sizes = _update_mm_sizes(mm_sizes)
    return JsonResponse(mm_sizes)


@require_deploy_apps
@quickcache(['domain', 'app_id', 'other_build_id', 'build_profile_id'], timeout=60 * 60)
def compare_multimedia_sizes(request, domain, app_id, other_build_id, build_profile_id=None):
    mm_sizes = get_new_multimedia_between_builds(domain, app_id, other_build_id, build_profile_id)
    if mm_sizes:
        mm_sizes = _update_mm_sizes(mm_sizes)
    return JsonResponse(mm_sizes)
