from __future__ import absolute_import
from django.http.response import Http404, HttpResponseForbidden, JsonResponse

from corehq.apps.app_manager.dbaccessors import get_app, get_latest_released_app
from corehq.apps.domain.decorators import api_key_auth


@api_key_auth
def get_latest_released_app_source(request, domain, app_id):
    master_app = get_app(None, app_id)
    if master_app.domain != domain:
        raise Http404

    requester = request.GET.get('requester')
    if requester not in master_app.linked_whitelist:
        return HttpResponseForbidden()

    latest_master_build = get_latest_released_app(domain, app_id)
    if not latest_master_build:
        raise Http404

    return JsonResponse(_convert_app_for_remote_linking(latest_master_build))


def _convert_app_for_remote_linking(latest_master_build):
    _attachments = latest_master_build.get_attachments()
    source = latest_master_build.to_json()
    source['_LAZY_ATTACHMENTS'] = {
        name: {'content': content}
        for name, content in _attachments.items()
    }
    source.pop("external_blobs", None)
    return source
