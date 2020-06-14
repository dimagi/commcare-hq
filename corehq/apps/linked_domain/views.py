from datetime import datetime

from django.contrib import messages
from django.db.models.expressions import RawSQL
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext, ugettext_lazy
from django.views import View

from couchdbkit import ResourceNotFound
from djng.views.mixins import JSONResponseMixin, allow_remote_invocation
from memoized import memoized

from corehq import toggles
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_brief_app_docs_in_domain,
    get_brief_apps_in_domain,
    get_build_doc_by_version,
    get_latest_released_app,
    get_latest_released_app_versions_by_app_id,
)
from corehq.apps.app_manager.decorators import require_can_edit_apps
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    CaseSearchQueryAddition,
)
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_or_api_key,
)
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pretty_doc_info
from corehq.apps.linked_domain.const import LINKED_MODELS, LINKED_MODELS_MAP, MODEL_CASE_SEARCH
from corehq.apps.linked_domain.dbaccessors import (
    get_domain_master_link,
    get_linked_domains,
)
from corehq.apps.linked_domain.decorators import require_linked_domain
from corehq.apps.linked_domain.local_accessors import (
    get_custom_data_models,
    get_toggles_previews,
    get_user_roles,
)
from corehq.apps.linked_domain.models import (
    AppLinkDetail,
    DomainLink,
    DomainLinkHistory,
    ReportLinkDetail,
    wrap_detail,
)
from corehq.apps.linked_domain.tasks import (
    pull_missing_multimedia_for_app_and_notify_task,
    push_models,
)
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import (
    convert_app_for_remote_linking,
    pull_missing_multimedia_for_app,
    server_to_user_time,
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
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
def brief_apps(request, domain):
    return JsonResponse({'brief_apps': get_brief_app_docs_in_domain(domain, include_remote=False)})


@login_or_api_key
@require_linked_domain
def app_by_version(request, domain, app_id, version):
    return JsonResponse({'app': get_build_doc_by_version(domain, app_id, version)})


@login_or_api_key
@require_linked_domain
def released_app_versions(request, domain):
    return JsonResponse({'versions': get_latest_released_app_versions_by_app_id(domain)})


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
def ucr_config(request, domain, config_id):
    report_config = ReportConfiguration.get(config_id)
    datasource_id = report_config.config_id
    datasource_config = DataSourceConfiguration.get(datasource_id)

    return JsonResponse({
        "report": report_config.to_json(),
        "datasource": datasource_config.to_json(),
    })


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


@require_can_edit_apps
def pull_missing_multimedia(request, domain, app_id):
    async_update = request.POST.get('notify') == 'on'
    if async_update:
        pull_missing_multimedia_for_app_and_notify_task.delay(domain, app_id, request.user.email)
        messages.success(request,
                         ugettext('Your request has been submitted. '
                                  'We will notify you via email once completed.'))
    else:
        app = get_app(domain, app_id)
        pull_missing_multimedia_for_app(app)
    return HttpResponseRedirect(reverse('app_settings', args=[domain, app_id]))


class DomainLinkView(BaseAdminProjectSettingsView):
    urlname = 'domain_links'
    page_title = ugettext_lazy("Linked Projects")
    template_name = 'linked_domain/domain_links.html'

    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        """
        This view services both domains that are master domains and domains that are linked domains
        (and legacy domains that are both).
        """
        timezone = get_timezone_for_request()
        master_link = get_domain_master_link(self.domain)
        linked_domains = [self._link_context(link, timezone) for link in get_linked_domains(self.domain)]
        (master_apps, linked_apps) = self._get_apps()
        (master_reports, linked_reports) = self._get_reports()

        # Models belonging to this domain's master domain, for the purpose of pulling
        model_status = self._get_model_status(master_link, linked_apps, linked_reports)

        # Models belonging to this domain, for the purpose of pushing to linked domains
        master_model_status = self._get_master_model_status(master_apps, master_reports)

        return {
            'domain': self.domain,
            'timezone': timezone.localize(datetime.utcnow()).tzname(),
            'is_linked_domain': bool(master_link),
            'is_master_domain': bool(len(linked_domains)),
            'view_data': {
                'master_link': self._link_context(master_link, timezone) if master_link else None,
                'model_status': sorted(model_status, key=lambda m: m['name']),
                'master_model_status': sorted(master_model_status, key=lambda m: m['name']),
                'linked_domains': linked_domains,
                'models': [
                    {'slug': model[0], 'name': model[1]}
                    for model in LINKED_MODELS
                ]
            },
        }

    def _get_apps(self):
        master_list = {}
        linked_list = {}
        briefs = get_brief_apps_in_domain(self.domain, include_remote=False)
        for brief in briefs:
            if is_linked_app(brief):
                linked_list[brief._id] = brief
            else:
                master_list[brief._id] = brief
        return (master_list, linked_list)

    def _get_reports(self):
        master_list = {}
        linked_list = {}
        reports = get_report_configs_for_domain(self.domain)
        for report in reports:
            if report.report_meta.master_id:
                linked_list[report.get_id] = report
            else:
                master_list[report.get_id] = report
        return (master_list, linked_list)

    def _link_context(self, link, timezone):
        return {
            'linked_domain': link.linked_domain,
            'master_domain': link.qualified_master,
            'remote_base_url': link.remote_base_url,
            'is_remote': link.is_remote,
            'last_update': server_to_user_time(link.last_pull, timezone) if link.last_pull else 'Never',
        }

    def _get_master_model_status(self, apps, reports, ignore_models=None):
        model_status = []
        ignore_models = ignore_models or []

        for model, name in LINKED_MODELS:
            if (
                model not in ignore_models
                and model not in ('app', 'report')
                and (model != MODEL_CASE_SEARCH or toggles.SYNC_SEARCH_CASE_CLAIM.enabled(self.domain))
            ):
                model_status.append({
                    'type': model,
                    'name': name,
                    'last_update': ugettext('Never'),
                    'detail': None,
                    'can_update': True
                })

        linked_models = dict(LINKED_MODELS)
        for app in apps.values():
            update = {
                'type': 'app',
                'name': '{} ({})'.format(linked_models['app'], app.name),
                'last_update': None,
                'detail': AppLinkDetail(app_id=app._id).to_json(),
                'can_update': True
            }
            model_status.append(update)
        for report in reports.values():
            report = ReportConfiguration.get(report.get_id)
            update = {
                'type': 'report',
                'name': f"{linked_models['report']} ({report.title})",
                'last_update': None,
                'detail': ReportLinkDetail(report_id=report.get_id).to_json(),
                'can_update': True,
            }
            model_status.append(update)

        return model_status

    def _get_model_status(self, master_link, apps, reports):
        model_status = []
        if not master_link:
            return model_status

        models_seen = set()
        history = DomainLinkHistory.objects.filter(link=master_link).annotate(row_number=RawSQL(
            'row_number() OVER (PARTITION BY model, model_detail ORDER BY date DESC)',
            []
        ))
        linked_models = dict(LINKED_MODELS)
        timezone = get_timezone_for_request()
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
                app_name = ugettext('Unknown App')
                if action.model_detail:
                    detail = action.wrapped_detail
                    app = apps.pop(detail.app_id, None)
                    app_name = app.name if app else detail.app_id
                    if app:
                        update['detail'] = action.model_detail
                    else:
                        update['can_update'] = False
                else:
                    update['can_update'] = False
                update['name'] = '{} ({})'.format(name, app_name)
            model_status.append(update)
            if action.model == 'report':
                report_id = action.wrapped_detail.report_id
                try:
                    report = reports.get(report_id)
                    del reports[report_id]
                except KeyError:
                    report = ReportConfiguration.get(report_id)
                update['name'] = f'{name} ({report.title})'

        # Add in models and apps that have never been synced
        model_status.extend(self._get_master_model_status(apps, reports, ignore_models=models_seen))

        return model_status


@method_decorator(domain_admin_required, name='dispatch')
class DomainLinkRMIView(JSONResponseMixin, View, DomainViewMixin):
    urlname = "domain_link_rmi"

    @allow_remote_invocation
    def update_linked_model(self, in_data):
        model = in_data['model']
        type_ = model['type']
        detail = model['detail']
        detail_obj = wrap_detail(type_, detail) if detail else None

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

    @allow_remote_invocation
    def create_release(self, in_data):
        push_models.delay(self.domain, in_data['models'], in_data['linked_domains'],
                          in_data['build_apps'], self.request.couch_user.username)
        return {
            'success': True,
            'message': ugettext('''
                Your release has begun. You will receive an email when it is complete.
                Until then, to avoid linked domains receiving inconsistent content, please
                avoid editing any of the data contained in the release.
            '''),
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
            if is_linked_app(app)
        }

    def _make_model_cell(self, record):
        name = LINKED_MODELS_MAP[record.model]
        if record.model == 'app':
            detail = record.wrapped_detail
            app_name = ugettext_lazy('Unknown App')
            if detail:
                app_names = self.linked_app_names(self.selected_link.linked_domain)
                app_name = app_names.get(detail.app_id, detail.app_id)
            return '{} ({})'.format(name, app_name)

        if record.model == 'report':
            detail = record.wrapped_detail
            report_name = ugettext_lazy('Unknown Report')
            if detail:
                try:
                    report_name = ReportConfiguration.get(detail.report_id).title
                except ResourceNotFound:
                    pass
            return '{} ({})'.format(name, report_name)

        return name

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
