import json
from collections import defaultdict

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from corehq import toggles
from corehq.apps.app_manager.views.apps import edit_app_attr

from dimagi.utils.web import json_response
from corehq.apps.domain.decorators import (
    login_and_domain_required,
)
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import no_conflict_require_POST, \
    require_can_edit_apps


@require_GET
@login_and_domain_required
def commcare_profile(request, domain, app_id):
    app = get_app(domain, app_id)
    return HttpResponse(json.dumps(app.profile))


@no_conflict_require_POST
@require_can_edit_apps
def edit_commcare_settings(request, domain, app_id):
    sub_responses = (
        edit_commcare_profile(request, domain, app_id),
        edit_app_attr(request, domain, app_id, 'all'),
    )
    response = {}
    for sub_response in sub_responses:
        response.update(
            json.loads(sub_response.content)
        )
    return json_response(response)


@no_conflict_require_POST
@require_can_edit_apps
def edit_commcare_profile(request, domain, app_id):
    try:
        settings = json.loads(request.body)
    except TypeError:
        return HttpResponseBadRequest(json.dumps({
            'reason': 'POST body must be of the form:'
            '{"properties": {...}, "features": {...}, "custom_properties": {...}}'
        }))
    app = get_app(domain, app_id)
    changed = defaultdict(dict)
    types = ["features", "properties"]

    if toggles.CUSTOM_PROPERTIES.enabled(domain):
        types.append("custom_properties")

    for settings_type in types:
        if settings_type == "custom_properties":
            app.profile[settings_type] = {}
        for name, value in settings.get(settings_type, {}).items():
            if settings_type not in app.profile:
                app.profile[settings_type] = {}
            app.profile[settings_type][name] = value
            changed[settings_type][name] = value
    response_json = {"status": "ok", "changed": changed}
    app.save(response_json)
    return json_response(response_json)
