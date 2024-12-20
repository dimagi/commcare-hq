import json
from collections import defaultdict

from django.contrib import messages
from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET
from django.views.generic.edit import FormView

from dimagi.utils.web import json_response

from corehq import toggles, privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import (
    no_conflict_require_POST,
    require_can_edit_apps,
)
from corehq.apps.app_manager.forms import PromptUpdateSettingsForm
from corehq.apps.app_manager.view_helpers import ApplicationViewMixin
from corehq.apps.app_manager.views.apps import edit_app_attr
from corehq.apps.domain.decorators import login_and_domain_required


@require_GET
@login_and_domain_required
def commcare_profile(request, domain, app_id):
    app = get_app(domain, app_id)
    return JsonResponse(app.profile, safe=False)


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
        settings = json.loads(request.body.decode('utf-8'))
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

    if not domain_has_privilege(domain, privileges.APP_DEPENDENCIES):
        # remove dependencies if they were set before
        if 'dependencies' in app.profile.get('features', {}):
            del app.profile['features']['dependencies']

    response_json = {"status": "ok", "changed": changed}
    app.save(response_json)
    return json_response(response_json)


@method_decorator(no_conflict_require_POST, name='dispatch')
@method_decorator(require_can_edit_apps, name='dispatch')
class PromptSettingsUpdateView(FormView, ApplicationViewMixin):
    form_class = PromptUpdateSettingsForm
    urlname = 'update_prompt_settings'

    @property
    def success_url(self):
        return reverse('release_manager', args=[self.domain, self.app_id])

    def get_form_kwargs(self):
        kwargs = super(PromptSettingsUpdateView, self).get_form_kwargs()
        kwargs.update({'domain': self.domain})
        kwargs.update({'app_id': self.app_id})
        kwargs.update({'request_user': self.request.couch_user})
        return kwargs

    def form_valid(self, form):
        config = self.app.global_app_config
        config.app_prompt = form.cleaned_data['app_prompt']
        config.apk_prompt = form.cleaned_data['apk_prompt']
        config.apk_version = form.cleaned_data['apk_version']
        config.app_version = form.cleaned_data['app_version']
        config.save()
        return super(PromptSettingsUpdateView, self).form_valid(form)

    def form_invalid(self, form):
        # Not a great UX, but this is just a guard against fabricated POST
        messages.error(self.request, form.errors)
        return HttpResponseRedirect(self.success_url)
