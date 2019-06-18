from __future__ import absolute_import, unicode_literals

from datetime import datetime

from django.db.models.expressions import RawSQL
from django.http import JsonResponse, Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy, ugettext
from django.views import View
from djangular.views.mixins import allow_remote_invocation, JSONResponseMixin

from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_brief_apps_in_domain,
    get_latest_released_app,
    get_latest_released_app_versions_by_app_id,
)
from corehq.apps.case_search.models import CaseSearchConfig, CaseSearchQueryAddition
from corehq.apps.domain.decorators import login_or_api_key, domain_admin_required
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pretty_doc_info
from corehq.apps.linked_domain.const import LINKED_MODELS, LINKED_MODELS_MAP
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link, get_linked_domains
from corehq.apps.linked_domain.decorators import require_linked_domain
from corehq.apps.linked_domain.local_accessors import get_toggles_previews, get_custom_data_models, get_user_roles
from corehq.apps.linked_domain.models import AppLinkDetail, wrap_detail, DomainLinkHistory, DomainLink
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import convert_app_for_remote_linking, server_to_user_time
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.util.timezones.utils import get_timezone_for_request
from memoized import memoized


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
def brief_apps(request, domain):
    return JsonResponse({'brief_apps': get_brief_apps_in_domain(domain, include_remote=False)})


@login_or_api_key
@require_linked_domain
def released_app_versions(request, domain):
    return JsonResponse({'versions': get_latest_released_app_versions_by_app_id(domain, include_remote=False)})


@login_or_api_key
@require_linked_domain
def case_search_config(request, domain):
    try:
        config = CaseSearchConfig.objects.get(domain=domain).to_json()
    except CaseSearchConfig.DoesNotExist:
        config = None

    try:
        addition = CaseSearchQueryAddition.objects.get(domain=domain).to_json()
    except CaseSearchQueryAddition.DoesNotExist:
        addition = None

    return JsonResponse({'config': config, 'addition': addition})


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


class DomainLinkView(BaseAdminProjectSettingsView):
    urlname = 'domain_links'
    page_title = ugettext_lazy("Linked Projects")
    template_name = 'linked_domain/domain_links.html'

    @property
    def page_context(self):
        timezone = get_timezone_for_request()

        def _link_context(link, timezone=timezone):
            return {
                'linked_domain': link.linked_domain,
                'master_domain': link.qualified_master,
                'remote_base_url': link.remote_base_url,
                'is_remote': link.is_remote,
                'last_update': server_to_user_time(link.last_pull, timezone) if link.last_pull else 'Never',
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
                'master_link': _link_context(master_link) if master_link else None,
                'model_status': sorted(model_status, key=lambda m: m['name']),
                'linked_domains': [
                    _link_context(link) for link in get_linked_domains(self.domain)
                ],
                'models': [
                    {'slug': model[0], 'name': model[1]}
                    for model in LINKED_MODELS
                ]
            },
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

        track_workflow(self.request.couch_user.username, "Linked domain: updated '{}' model".format(type_))

        timezone = get_timezone_for_request()
        return {
            'success': True,
            'last_update': server_to_user_time(master_link.last_pull, timezone)
        }

    @allow_remote_invocation
    def delete_domain_link(self, in_data):
        linked_domain = in_data['linked_domain']
        link = DomainLink.objects.filter(linked_domain=linked_domain, master_domain=self.domain).first()
        link.deleted = True
        link.save()

        track_workflow(self.request.couch_user.username, "Linked domain: domain link deleted")

        return {
            'success': True,
        }


class DomainLinkHistoryReport(GenericTabularReport):
    name = 'Linked Project History'
    base_template = "reports/base_template.html"
    section_name = 'Project Settings'
    slug = 'project_link_report'
    dispatcher = DomainReportDispatcher
    ajax_pagination = True
    asynchronous = False
    sortable = False

    @property
    def fields(self):
        if self.master_link:
            fields = []
        else:
            fields = ['corehq.apps.linked_domain.filters.DomainLinkFilter']
        fields.append('corehq.apps.linked_domain.filters.DomainLinkModelFilter')
        return fields

    @property
    def link_model(self):
        return self.request.GET.get('domain_link_model')

    @property
    @memoized
    def domain_link(self):
        if self.request.GET.get('domain_link'):
            try:
                return DomainLink.all_objects.get(
                    pk=self.request.GET.get('domain_link'),
                    master_domain=self.domain
                )
            except DomainLink.DoesNotExist:
                pass

    @property
    @memoized
    def master_link(self):
        return get_domain_master_link(self.domain)

    @property
    @memoized
    def selected_link(self):
        return self.master_link or self.domain_link

    @property
    def total_records(self):
        query = self._base_query()
        return query.count()

    def _base_query(self):
        query = DomainLinkHistory.objects.filter(link=self.selected_link)
        if self.link_model:
            query = query.filter(model=self.link_model)

        return query

    @property
    def shared_pagination_GET_params(self):
        link_id = str(self.selected_link.pk) if self.selected_link else ''
        return [
            {'name': 'domain_link', 'value': link_id},
            {'name': 'domain_link_model', 'value': self.link_model},
        ]

    @property
    def rows(self):
        if not self.selected_link:
            return []
        rows = self._base_query()[self.pagination.start:self.pagination.start + self.pagination.count + 1]
        return [self._make_row(record, self.selected_link) for record in rows]

    def _make_row(self, record, link):
        row = [
            '{} -> {}'.format(link.master_domain, link.linked_domain),
            server_to_user_time(record.date, self.timezone),
            self._make_model_cell(record),
            pretty_doc_info(get_doc_info_by_id(self.domain, record.user_id))
        ]
        return row

    @memoized
    def linked_app_names(self, domain):
        return {
            app._id: app.name for app in get_brief_apps_in_domain(domain)
            if app.doc_type == 'LinkedApplication'
        }

    def _make_model_cell(self, record):
        name = LINKED_MODELS_MAP[record.model]
        if record.model != 'app':
            return name

        detail = record.wrapped_detail
        app_name = 'Unknown App'
        if detail:
            app_names = self.linked_app_names(self.selected_link.linked_domain)
            app_name = app_names.get(detail.app_id, detail.app_id)
        return '{} ({})'.format(name, app_name)

    @property
    def headers(self):
        tzname = self.timezone.localize(datetime.utcnow()).tzname()
        columns = [
            DataTablesColumn(ugettext('Link')),
            DataTablesColumn(ugettext('Date ({})'.format(tzname))),
            DataTablesColumn(ugettext('Data Model')),
            DataTablesColumn(ugettext('User')),
        ]

        return DataTablesHeader(*columns)
