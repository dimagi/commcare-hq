from __future__ import absolute_import

from datetime import datetime

from django.db.models.expressions import RawSQL
from django.http import JsonResponse, Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy, ugettext
from django.views import View
from djangular.views.mixins import allow_remote_invocation, JSONResponseMixin

from corehq.apps.app_manager.dbaccessors import get_latest_released_app, get_app, get_brief_apps_in_domain
from corehq.apps.domain.decorators import login_or_api_key, domain_admin_required
from corehq.apps.domain.views import BaseAdminProjectSettingsView, DomainViewMixin
from corehq.apps.linked_domain.const import LINKED_MODELS
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link, get_linked_domains
from corehq.apps.linked_domain.decorators import require_linked_domain
from corehq.apps.linked_domain.local_accessors import get_toggles_previews, get_custom_data_models, get_user_roles
from corehq.apps.linked_domain.models import AppLinkDetail, wrap_detail, DomainLinkHistory
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import convert_app_for_remote_linking, server_to_user_time
from corehq.util.timezones.utils import get_timezone_for_request


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
@require_linked_domain
def get_latest_released_app_source(request, domain, app_id):
    master_app = get_app(None, app_id)
    if master_app.domain != domain:
        raise Http404

    latest_master_build = get_latest_released_app(domain, app_id)
    if not latest_master_build:
        raise Http404

    return JsonResponse(convert_app_for_remote_linking(latest_master_build))


@method_decorator(domain_admin_required, name='dispatch')
class DomainLinkView(BaseAdminProjectSettingsView):
    urlname = 'linked_domain:domain_links'
    urlname_plain = 'domain_links'
    page_title = ugettext_lazy("Domain Links")
    template_name = 'linked_domain/domain_links.html'

    @property
    def page_context(self):
        timezone = get_timezone_for_request()

        def _link_context(link):
            return {
                'linked_domain': link.linked_domain,
                'master_domain': link.qualified_master,
                'is_remote': link.is_remote,
                'last_update': server_to_user_time(link.last_pull, timezone),
            }

        model_status = []
        linked_models = dict(LINKED_MODELS)
        master_link = get_domain_master_link(self.domain)
        if master_link:
            linked_apps = {
                app._id: app for app in get_brief_apps_in_domain(self.domain)
                if app.doc_type == 'LinkedApplication'
            }
            models_seen = set()
            history = DomainLinkHistory.objects.filter(link=master_link).annotate(row_number=RawSQL(
                'row_number() OVER (PARTITION BY model, model_detail ORDER BY date DESC)',
                []
            ))
            for action in history:
                print(action.model, action.date, action.row_number)
                models_seen.add(action.model)
                if action.row_number != 1:
                    # first row is the most recent
                    continue
                name = linked_models[action.model]
                update = {
                    'type': action.model,
                    'name': name,
                    'last_update': server_to_user_time(action.date, timezone),
                    'detail': action.model_detail,
                    'can_update': True
                }
                if action.model == 'app':
                    app_name = 'Unknown App'
                    if action.model_detail:
                        detail = action.wrapped_detail
                        app = linked_apps.pop(detail.app_id, None)
                        app_name = app.name if app else detail.app_id
                        if app:
                            update['detail'] = action.model_detail
                        else:
                            update['can_update'] = False
                    else:
                        update['can_update'] = False
                    update['name'] = '{} ({})'.format(name, app_name)
                model_status.append(update)

            # Add in models that have never been synced
            for model, name in LINKED_MODELS:
                if model not in models_seen and model != 'app':
                    model_status.append({
                        'type': model,
                        'name': name,
                        'last_update': ugettext('Never'),
                        'detail': None,
                        'can_update': True
                    })

            # Add in apps that have never been synced
            if linked_apps:
                for app in linked_apps.values():
                    update = {
                        'type': 'app',
                        'name': '{} ({})'.format(linked_models['app'], app.name),
                        'last_update': None,
                        'detail': AppLinkDetail(app_id=app._id).to_json(),
                        'can_update': True
                    }
                    model_status.append(update)

        return {
            'domain': self.domain,
            'timezone': timezone.localize(datetime.utcnow()).tzname(),
            'view_data': {
                'master_link': _link_context(master_link),
                'model_status': sorted(model_status, key=lambda m: m['name']),
                'linked_domains': [
                    _link_context(link) for link in get_linked_domains(self.domain)
                ],
                'models': [
                    {'slug': model[0], 'name': model[1]}
                    for model in LINKED_MODELS
                ]
            }
        }


@method_decorator(domain_admin_required, name='dispatch')
class DomainLinkRMIView(JSONResponseMixin, View, DomainViewMixin):
    urlname = "domain_link_rmi"

    @allow_remote_invocation
    def update_linked_model(self, in_data):
        model = in_data['model']
        type_ = model['type']
        detail = model['detail']
        detail_obj = wrap_detail(type, detail) if detail else None

        master_link = get_domain_master_link(self.domain)
        update_model_type(master_link, type_, detail_obj)
        master_link.update_last_pull(type_, self.request.couch_user._id, model_details=detail_obj)

        timezone = get_timezone_for_request()
        return {
            'success': True,
            'last_update': server_to_user_time(master_link.last_pull, timezone)
        }
