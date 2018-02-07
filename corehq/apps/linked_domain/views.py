from __future__ import absolute_import
from django.http import JsonResponse, Http404, HttpResponseForbidden

from corehq.apps.app_manager.dbaccessors import get_latest_released_app, get_app
from corehq.apps.domain.decorators import api_key_auth, login_or_api_key
from corehq.apps.linked_domain.decorators import require_linked_domain
from corehq.apps.linked_domain.local_accessors import get_toggles_previews, get_custom_data_models, get_user_roles
from corehq.apps.linked_domain.util import convert_app_for_remote_linking


@login_or_api_key
@require_linked_domain
def toggles_and_previews(request, domain):
    return JsonResponse(get_toggles_previews(domain))


@login_or_api_key
@require_linked_domain
def custom_data_models(request, domain):
    limit_types = request.GET.getlist('type')
    return JsonResponse(get_custom_data_models(domain, limit_types))


@login_or_api_key
@require_linked_domain
def user_roles(request, domain):
    return JsonResponse({'user_roles': get_user_roles(domain)})


@login_or_api_key
# @require_linked_domain  # need to migrate whitelist before we can put this here
def get_latest_released_app_source(request, domain, app_id):
    master_app = get_app(None, app_id)
    if master_app.domain != domain:
        raise Http404

    requester = request.META.get('HTTP_HQ_REMOTE_REQUESTER', None)
    if requester not in master_app.linked_whitelist:
        return HttpResponseForbidden()

    latest_master_build = get_latest_released_app(domain, app_id)
    if not latest_master_build:
        raise Http404

    return JsonResponse(convert_app_for_remote_linking(latest_master_build))
