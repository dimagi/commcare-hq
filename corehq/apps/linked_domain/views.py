from datetime import datetime

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext, ugettext_lazy
from django.views import View

from couchdbkit import ResourceNotFound
from djng.views.mixins import JSONResponseMixin, allow_remote_invocation
from memoized import memoized

from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import domain_has_privilege
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
from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_or_api_key,
)
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView
from corehq.apps.fixtures.dbaccessors import get_fixture_data_type_by_tag
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pretty_doc_info
from corehq.apps.linked_domain.const import (
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_FIXTURE,
    MODEL_KEYWORD,
    MODEL_REPORT,
    SUPERUSER_DATA_MODELS,
)
from corehq.apps.linked_domain.dbaccessors import (
    get_available_domains_to_link,
    get_linked_domains,
    get_upstream_domain_link,
    get_upstream_domains,
)
from corehq.apps.linked_domain.decorators import require_linked_domain, require_access_to_linked_domains
from corehq.apps.linked_domain.exceptions import (
    DomainLinkError,
    UnsupportedActionError,
)
from corehq.apps.linked_domain.local_accessors import (
    get_custom_data_models,
    get_data_dictionary,
    get_dialer_settings,
    get_enabled_toggles_and_previews,
    get_fixture,
    get_hmac_callout_settings,
    get_otp_settings,
    get_user_roles,
)
from corehq.apps.linked_domain.models import (
    DomainLink,
    DomainLinkHistory,
    wrap_detail,
)
from corehq.apps.linked_domain.remote_accessors import get_remote_linkable_ucr
from corehq.apps.linked_domain.tasks import (
    pull_missing_multimedia_for_app_and_notify_task,
    push_models,
)
from corehq.apps.linked_domain.ucr import create_linked_ucr
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import (
    convert_app_for_remote_linking,
    pull_missing_multimedia_for_app,
    server_to_user_time,
)
from corehq.apps.linked_domain.view_helpers import (
    build_domain_link_view_model,
    build_pullable_view_models_from_data_models,
    build_view_models_from_data_models,
    get_apps,
    get_fixtures,
    get_keywords,
    get_reports,
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import ReleaseManagementReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.privileges import RELEASE_MANAGEMENT
from corehq.util.timezones.utils import get_timezone_for_request


@login_or_api_key
@require_linked_domain
def toggles_and_previews(request, domain):
    return JsonResponse(get_enabled_toggles_and_previews(domain))


@login_or_api_key
@require_linked_domain
def custom_data_models(request, domain):
    limit_types = request.GET.getlist('type')
    return JsonResponse(get_custom_data_models(domain, limit_types))


@login_or_api_key
@require_linked_domain
def fixture(request, domain, tag):
    return JsonResponse(get_fixture(domain, tag))


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

    return JsonResponse({'config': config})


@login_or_api_key
@require_linked_domain
@require_permission(Permissions.view_reports)
def linkable_ucr(request, domain):
    """Returns a list of reports to be used by the downstream
    domain on a remote server to create linked reports by calling the
    `ucr_config` view below

    """
    reports = get_report_configs_for_domain(domain)
    return JsonResponse({
        "reports": [
            {"id": report._id, "title": report.title} for report in reports]
    })


@login_or_api_key
@require_linked_domain
def ucr_config(request, domain, config_id):
    report_config = ReportConfiguration.get(config_id)
    if report_config.domain != domain:
        return Http404
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


@login_or_api_key
@require_linked_domain
def data_dictionary(request, domain):
    return JsonResponse(get_data_dictionary(domain))


@login_or_api_key
@require_linked_domain
def dialer_settings(request, domain):
    return JsonResponse(get_dialer_settings(domain))


@login_or_api_key
@require_linked_domain
def otp_settings(request, domain):
    return JsonResponse(get_otp_settings(domain))


@login_or_api_key
@require_linked_domain
def hmac_callout_settings(request, domain):
    return JsonResponse(get_hmac_callout_settings(domain))


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


@method_decorator(require_access_to_linked_domains, name='dispatch')
class DomainLinkView(BaseAdminProjectSettingsView):
    urlname = 'domain_links'
    page_title = ugettext_lazy("Linked Project Spaces")
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
        master_link = get_upstream_domain_link(self.domain)
        linked_domains = [build_domain_link_view_model(link, timezone) for link in get_linked_domains(self.domain)]
        master_apps, linked_apps = get_apps(self.domain)
        master_fixtures, linked_fixtures = get_fixtures(self.domain, master_link)
        master_reports, linked_reports = get_reports(self.domain)
        master_keywords, linked_keywords = get_keywords(self.domain)

        is_superuser = self.request.couch_user.is_superuser
        timezone = get_timezone_for_request()
        view_models_to_pull = build_pullable_view_models_from_data_models(
            self.domain, master_link, linked_apps, linked_fixtures, linked_reports, linked_keywords, timezone,
            is_superuser=is_superuser
        )

        view_models_to_push = build_view_models_from_data_models(
            self.domain, master_apps, master_fixtures, master_reports, master_keywords, is_superuser=is_superuser
        )

        current_subscription = Subscription.get_active_subscription_by_domain(self.request.domain)
        available_domains_to_link = get_available_domains_to_link(self.request.domain,
                                                                  self.request.couch_user,
                                                                  billing_account=current_subscription.account)
        upstream_domains = []
        for domain in get_upstream_domains(self.request.domain, self.request.couch_user):
            upstream_domains.append({'name': domain, 'url': reverse('domain_links', args=[domain])})

        if master_link and master_link.is_remote:
            remote_linkable_ucr = get_remote_linkable_ucr(master_link)
        else:
            remote_linkable_ucr = None

        return {
            'domain': self.domain,
            'timezone': timezone.localize(datetime.utcnow()).tzname(),
            'has_release_management_privilege': domain_has_privilege(self.domain, RELEASE_MANAGEMENT),
            'view_data': {
                'is_downstream_domain': bool(master_link),
                'upstream_domains': upstream_domains,
                'available_domains': available_domains_to_link,
                'master_link': build_domain_link_view_model(master_link, timezone) if master_link else None,
                'model_status': sorted(view_models_to_pull, key=lambda m: m['name']),
                'master_model_status': sorted(view_models_to_push, key=lambda m: m['name']),
                'linked_domains': sorted(linked_domains, key=lambda d: d['linked_domain']),
                'linkable_ucr': remote_linkable_ucr,
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
        detail_obj = wrap_detail(type_, detail) if detail else None

        master_link = get_upstream_domain_link(self.domain)
        error = ""
        try:
            update_model_type(master_link, type_, detail_obj)
            model_detail = detail_obj.to_json() if detail_obj else None
            master_link.update_last_pull(type_, self.request.couch_user._id, model_detail=model_detail)
        except (DomainLinkError, UnsupportedActionError) as e:
            error = str(e)

        track_workflow(self.request.couch_user.username, "Linked domain: updated '{}' model".format(type_))

        timezone = get_timezone_for_request()
        return {
            'success': not error,
            'error': error,
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

    @allow_remote_invocation
    def create_domain_link(self, in_data):
        domain_to_link = in_data['downstream_domain']
        try:
            domain_link = DomainLink.link_domains(domain_to_link, self.domain)
        except DomainLinkError as e:
            return {
                'success': False,
                'message': str(e)
            }

        timezone = get_timezone_for_request()
        return {
            'success': True,
            'domain_link': build_domain_link_view_model(domain_link, timezone)
        }

    def create_remote_report_link(self, in_data):
        linked_domain = in_data['linked_domain']
        master_domain = in_data['master_domain'].strip('/').split('/')[-1]
        report_id = in_data['report_id']
        link = DomainLink.objects.filter(
            remote_base_url__isnull=False,
            linked_domain=linked_domain,
            master_domain=master_domain,
        ).first()
        if link:
            create_linked_ucr(link, report_id)
            return {'success': True}
        else:
            return {'success': False}


class DomainLinkHistoryReport(GenericTabularReport):
    name = 'Linked Project Space History'
    base_template = "reports/base_template.html"
    section_name = 'Project Settings'
    slug = 'project_link_report'
    dispatcher = ReleaseManagementReportDispatcher
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
        return get_upstream_domain_link(self.domain)

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

        # filter out superuser data models
        if not self.request.couch_user.is_superuser:
            query = query.exclude(model__in=dict(SUPERUSER_DATA_MODELS).keys())

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
        if record.model == MODEL_APP:
            detail = record.wrapped_detail
            app_name = ugettext_lazy('Unknown App')
            if detail:
                app_names = self.linked_app_names(self.selected_link.linked_domain)
                app_name = app_names.get(detail.app_id, detail.app_id)
            return '{} ({})'.format(name, app_name)

        if record.model == MODEL_FIXTURE:
            detail = record.wrapped_detail
            tag = ugettext_lazy('Unknown')
            if detail:
                data_type = get_fixture_data_type_by_tag(self.selected_link.linked_domain, detail.tag)
                if data_type:
                    tag = data_type.tag
            return '{} ({})'.format(name, tag)

        if record.model == MODEL_REPORT:
            detail = record.wrapped_detail
            report_name = ugettext_lazy('Unknown Report')
            if detail:
                try:
                    report_name = ReportConfiguration.get(detail.report_id).title
                except ResourceNotFound:
                    pass
            return '{} ({})'.format(name, report_name)

        if record.model == MODEL_KEYWORD:
            detail = record.wrapped_detail
            keyword_name = ugettext_lazy('Unknown Keyword')
            if detail:
                try:
                    keyword_name = Keyword.objects.get(id=detail.keyword_id).keyword
                except Keyword.DoesNotExist:
                    pass
            return f'{name} ({keyword_name})'

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
