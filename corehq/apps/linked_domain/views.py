from datetime import datetime

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext, gettext_lazy
from django.views import View

from couchdbkit import ResourceNotFound
from memoized import memoized

from dimagi.utils.logging import notify_exception

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
from corehq.apps.domain.dbaccessors import domain_exists
from corehq.apps.domain.decorators import login_or_api_key
from corehq.apps.domain.exceptions import DomainDoesNotExist
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.fixtures.models import LookupTable
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
    get_active_domain_link,
    get_available_domains_to_link,
    get_available_upstream_domains,
    get_linked_domains,
    get_upstream_domain_link,
)
from corehq.apps.linked_domain.decorators import require_access_to_linked_domains
from corehq.apps.linked_domain.exceptions import (
    DomainLinkAlreadyExists,
    DomainLinkError,
    DomainLinkNotAllowed,
    InvalidPushException,
    UnsupportedActionError,
    UserDoesNotHavePermission,
)
from corehq.apps.linked_domain.local_accessors import (
    get_auto_update_rules,
    get_custom_data_models,
    get_data_dictionary,
    get_dialer_settings,
    get_enabled_toggles_and_previews,
    get_fixture,
    get_hmac_callout_settings,
    get_otp_settings,
    get_tableau_server_and_visualizations,
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
    can_domain_access_linked_domains,
    convert_app_for_remote_linking,
    pull_missing_multimedia_for_app,
    server_to_user_time,
    user_has_access,
    user_has_access_in_all_domains,
)
from corehq.apps.linked_domain.view_helpers import (
    build_domain_link_view_model,
    build_pullable_view_models_from_data_models,
    build_view_models_from_data_models,
    get_upstream_and_downstream_apps,
    get_upstream_and_downstream_fixtures,
    get_upstream_and_downstream_keywords,
    get_upstream_and_downstream_reports,
    get_upstream_and_downstream_ucr_expressions,
    get_upstream_and_downstream_update_rules
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import ReleaseManagementReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.dbaccessors import get_report_and_registry_report_configs_for_domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.util.jqueryrmi import JSONResponseMixin, allow_remote_invocation
from corehq.util.timezones.utils import get_timezone_for_request


@login_or_api_key
@require_access_to_linked_domains
def tableau_server_and_visualizations(request, domain):
    return JsonResponse(get_tableau_server_and_visualizations(domain))


@login_or_api_key
@require_access_to_linked_domains
def toggles_and_previews(request, domain):
    return JsonResponse(get_enabled_toggles_and_previews(domain))


@login_or_api_key
@require_access_to_linked_domains
def auto_update_rules(request, domain):
    return JsonResponse({'rules': get_auto_update_rules(domain)})


@login_or_api_key
@require_access_to_linked_domains
def custom_data_models(request, domain):
    limit_types = request.GET.getlist('type')
    return JsonResponse(get_custom_data_models(domain, limit_types))


@login_or_api_key
@require_access_to_linked_domains
def fixture(request, domain, tag):
    return JsonResponse(get_fixture(domain, tag))


@login_or_api_key
@require_access_to_linked_domains
def user_roles(request, domain):
    return JsonResponse({'user_roles': get_user_roles(domain)})


@login_or_api_key
@require_access_to_linked_domains
def brief_apps(request, domain):
    return JsonResponse({'brief_apps': get_brief_app_docs_in_domain(domain, include_remote=False)})


@login_or_api_key
@require_access_to_linked_domains
def app_by_version(request, domain, app_id, version):
    return JsonResponse({'app': get_build_doc_by_version(domain, app_id, version)})


@login_or_api_key
@require_access_to_linked_domains
def released_app_versions(request, domain):
    return JsonResponse({'versions': get_latest_released_app_versions_by_app_id(domain)})


@login_or_api_key
@require_access_to_linked_domains
def case_search_config(request, domain):
    try:
        config = CaseSearchConfig.objects.get(domain=domain).to_json()
    except CaseSearchConfig.DoesNotExist:
        config = None

    return JsonResponse({'config': config})


@login_or_api_key
@require_access_to_linked_domains
@require_permission(HqPermissions.view_reports)
def linkable_ucr(request, domain):
    """Returns a list of reports to be used by the downstream
    domain on a remote server to create linked reports by calling the
    `ucr_config` view below

    """
    reports = get_report_and_registry_report_configs_for_domain(domain)
    return JsonResponse({
        "reports": [
            {"id": report._id, "title": report.title} for report in reports]
    })


@login_or_api_key
@require_access_to_linked_domains
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
@require_access_to_linked_domains
def get_latest_released_app_source(request, domain, app_id):
    master_app = get_app(None, app_id)
    if master_app.domain != domain:
        raise Http404

    latest_master_build = get_latest_released_app(domain, app_id)
    if not latest_master_build:
        raise Http404

    return JsonResponse(convert_app_for_remote_linking(latest_master_build))


@login_or_api_key
@require_access_to_linked_domains
def data_dictionary(request, domain):
    return JsonResponse(get_data_dictionary(domain))


@login_or_api_key
@require_access_to_linked_domains
def dialer_settings(request, domain):
    return JsonResponse(get_dialer_settings(domain))


@login_or_api_key
@require_access_to_linked_domains
def otp_settings(request, domain):
    return JsonResponse(get_otp_settings(domain))


@login_or_api_key
@require_access_to_linked_domains
def hmac_callout_settings(request, domain):
    return JsonResponse(get_hmac_callout_settings(domain))


@require_can_edit_apps
def pull_missing_multimedia(request, domain, app_id):
    async_update = request.POST.get('notify') == 'on'
    force = request.POST.get('force') == 'on'
    if async_update:
        pull_missing_multimedia_for_app_and_notify_task.delay(domain, app_id, request.user.email, force)
        messages.success(request,
                         gettext('Your request has been submitted. '
                                 'We will notify you via email once completed.'))
    else:
        app = get_app(domain, app_id)
        pull_missing_multimedia_for_app(app, force=force)
    return HttpResponseRedirect(reverse('app_settings', args=[domain, app_id]))


@method_decorator(require_access_to_linked_domains, name='dispatch')
class DomainLinkView(BaseProjectSettingsView):
    urlname = 'domain_links'
    page_title = gettext_lazy("Linked Project Spaces")
    template_name = 'linked_domain/domain_links.html'

    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        """
        This view services both domains that are upstream, downstream, and legacy domains that are both
        """
        timezone = get_timezone_for_request()
        upstream_link = get_upstream_domain_link(self.domain)
        linked_domains = [build_domain_link_view_model(link, timezone) for link in get_linked_domains(self.domain)]
        upstream_apps, downstream_apps = get_upstream_and_downstream_apps(self.domain)
        upstream_fixtures, downstream_fixtures = get_upstream_and_downstream_fixtures(self.domain, upstream_link)
        upstream_reports, downstream_reports = get_upstream_and_downstream_reports(self.domain)
        upstream_keywords, downstream_keywords = get_upstream_and_downstream_keywords(self.domain)
        upstream_ucr_expressions, downstream_ucr_expressions = get_upstream_and_downstream_ucr_expressions(
            self.domain
        )

        upstream_rules, downstream_rules = get_upstream_and_downstream_update_rules(self.domain, upstream_link)

        is_superuser = self.request.couch_user.is_superuser
        timezone = get_timezone_for_request()
        view_models_to_pull = build_pullable_view_models_from_data_models(
            self.domain,
            upstream_link,
            downstream_apps,
            downstream_fixtures,
            downstream_reports,
            downstream_keywords,
            downstream_ucr_expressions,
            downstream_rules,
            timezone,
            is_superuser=is_superuser
        )

        view_models_to_push = build_view_models_from_data_models(
            self.domain,
            upstream_apps,
            upstream_fixtures,
            upstream_reports,
            upstream_keywords,
            upstream_ucr_expressions,
            upstream_rules,
            is_superuser=is_superuser
        )

        available_domains_to_link = get_available_domains_to_link(self.request.domain, self.request.couch_user)

        upstream_domain_urls = []
        for domain in get_available_upstream_domains(self.request.domain, self.request.couch_user):
            upstream_domain_urls.append({'name': domain, 'url': reverse('domain_links', args=[domain])})

        if upstream_link and upstream_link.is_remote:
            remote_linkable_ucr = get_remote_linkable_ucr(upstream_link)
        else:
            remote_linkable_ucr = None

        linked_status = None
        if upstream_link:
            linked_status = 'downstream'
            track_workflow(
                self.request.couch_user.username,
                'Lands on feature page (downstream)',
                {'domain': self.domain}
            )
        elif linked_domains:
            linked_status = 'upstream'
            track_workflow(
                self.request.couch_user.username,
                'Lands on feature page (upstream)',
                {'domain': self.domain}
            )

        return {
            'domain': self.domain,
            'timezone': timezone.localize(datetime.utcnow()).tzname(),
            'linked_status': linked_status,
            'view_data': {
                'domain': self.domain,
                'is_superuser': is_superuser,
                'is_downstream_domain': bool(upstream_link),
                'upstream_domains': upstream_domain_urls,
                'available_domains': available_domains_to_link,
                'upstream_link': build_domain_link_view_model(upstream_link, timezone) if upstream_link else None,
                'view_models_to_pull': sorted(view_models_to_pull, key=lambda m: m['name']),
                'view_models_to_push': sorted(view_models_to_push, key=lambda m: m['name']),
                'linked_domains': sorted(linked_domains, key=lambda d: d['downstream_domain']),
                'linkable_ucr': remote_linkable_ucr,
                'has_full_access': can_domain_access_linked_domains(self.domain, include_lite_version=False),
            },
        }


@method_decorator(require_access_to_linked_domains, name='dispatch')
class DomainLinkRMIView(JSONResponseMixin, View, DomainViewMixin):
    urlname = "domain_link_rmi"

    @allow_remote_invocation
    def update_linked_model(self, in_data):
        model = in_data['model']
        type_ = model['type']
        detail = model['detail']
        detail_obj = wrap_detail(type_, detail) if detail else None
        timezone = get_timezone_for_request()
        domain_link = get_upstream_domain_link(self.domain)
        overwrite = in_data['overwrite'] or False

        try:
            validate_pull(self.request.couch_user, domain_link)
        except UserDoesNotHavePermission:
            notify_exception(self.request, "Triggered UserDoesNotHavePermission exception")
            return {
                'success': False,
                'error': gettext(
                    "You do not have permission to pull content into this project space."
                ),
                'last_update': server_to_user_time(domain_link.last_pull, timezone),
            }

        error = ""
        try:
            update_model_type(domain_link, type_, detail_obj, is_pull=True, overwrite=overwrite)
            model_detail = detail_obj.to_json() if detail_obj else None
            domain_link.update_last_pull(type_, self.request.couch_user._id, model_detail=model_detail)
        except (DomainLinkError, UnsupportedActionError) as e:
            error = str(e)

        metric_name = "Linked domain: pulled and overwrote data model" \
            if overwrite else "Linked domain: pulled data model"
        track_workflow(
            self.request.couch_user.username,
            metric_name,
            {
                'domain': self.domain,
                'data_model': type_,
            }
        )

        return {
            'success': not error,
            'error': error,
            'last_update': server_to_user_time(domain_link.last_pull, timezone)
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
        try:
            validate_push(self.request.couch_user, self.domain, in_data['linked_domains'])
        except InvalidPushException as e:
            return {
                'success': False,
                'message': e.message,
            }

        overwrite = in_data.get('overwrite', False)

        push_models.delay(self.domain, in_data['models'], in_data['linked_domains'],
                          in_data['build_apps'], self.request.couch_user.username, overwrite)

        metric_args = {
            'domain': self.domain,
            'build_apps': in_data['build_apps'],
            'data_models': in_data['models'],
        }
        metric_name = "Linked domain: pushed and overwrote data models" \
            if overwrite else "Linked domain: pushed data models"

        track_workflow(self.request.couch_user.username, metric_name, metric_args)

        return {
            'success': True,
            'message': gettext('''
                Your release has begun. You will receive an email when it is complete.
                Until then, to avoid linked domains receiving inconsistent content, please
                avoid editing any of the data contained in the release.
            '''),
        }

    @allow_remote_invocation
    def create_domain_link(self, in_data):
        domain_to_link = in_data['downstream_domain']
        try:
            domain_link = link_domains(self.request.couch_user, self.domain, domain_to_link)
        except (DomainDoesNotExist, DomainLinkAlreadyExists, DomainLinkNotAllowed, DomainLinkError) as e:
            return {'success': False, 'message': str(e)}

        track_workflow(self.request.couch_user.username, "Linked domain: domain link created")

        domain_link_view_model = build_domain_link_view_model(domain_link, get_timezone_for_request())
        return {'success': True, 'domain_link': domain_link_view_model}

    @allow_remote_invocation
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


def link_domains(couch_user, upstream_domain, downstream_domain):
    if not domain_exists(downstream_domain):
        error = gettext("The project space {} does not exist. Verify that the name is correct, and that the "
                        "domain has not been deleted.").format(downstream_domain)
        raise DomainDoesNotExist(error)

    if get_active_domain_link(upstream_domain, downstream_domain):
        error = gettext(
            "The project space {} is already a downstream project space of {}."
        ).format(downstream_domain, upstream_domain)
        raise DomainLinkAlreadyExists(error)

    if not user_has_access_in_all_domains(couch_user, [upstream_domain, downstream_domain]):
        error = gettext("You do not have adequate permissions in both project spaces to create a link.")
        raise DomainLinkNotAllowed(error)

    return DomainLink.link_domains(downstream_domain, upstream_domain)


def validate_push(user, domain, downstream_domains):
    if not downstream_domains:
        raise InvalidPushException(
            message=gettext("No downstream project spaces were selected. Please contact support.")
        )

    domain_links = []
    for dd in downstream_domains:
        try:
            domain_links.append(DomainLink.objects.get(master_domain=domain, linked_domain=dd))
        except DomainLink.DoesNotExist:
            raise InvalidPushException(
                message=gettext(
                    "The project space link between {} and {} does not exist. Ensure the link was not recently "
                    "deleted.").format(domain, dd)
            )

    if not user_has_access_in_all_domains(user, downstream_domains):
        raise InvalidPushException(
            message=gettext("You do not have permission to push to all specified downstream project spaces.")
        )

    check_if_push_violates_constraints(user, domain_links)


def check_if_push_violates_constraints(user, domain_links):
    """
    Ensures MRM limit of pushing to 1 domain at a time is enforced
    """
    if user.is_superuser:
        return

    if len(domain_links) == 1:
        # pushing to one domain is fine regardless of access status
        return

    limited_access_links = list(filter(lambda link: not link.has_full_access(), domain_links))

    if not limited_access_links:
        # all links are full access
        return

    limited_domains = [d.linked_domain for d in limited_access_links]
    error_message = gettext(
        "The attempted push is disallowed because it includes the following domains that can only be pushed to "
        "one at a time: {}".format(', '.join(limited_domains)))
    raise InvalidPushException(message=error_message)


def validate_pull(user, domain_link):
    # ensure user has access in the downstream domain
    if not user_has_access(user, domain_link.linked_domain):
        raise UserDoesNotHavePermission


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
        if self.upstream_link:
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
    def upstream_link(self):
        return get_upstream_domain_link(self.domain)

    @property
    @memoized
    def selected_link(self):
        return self.upstream_link or self.domain_link

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
            self._make_user_cell(record)
        ]
        return row

    def _make_user_cell(self, record):
        doc_info = get_doc_info_by_id(self.domain, record.user_id)
        user = WebUser.get_by_user_id(record.user_id)
        if user and self.domain not in user.get_domains() and 'link' in doc_info:
            doc_info['link'] = None

        return pretty_doc_info(doc_info)

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
            app_name = gettext_lazy('Unknown App')
            if detail:
                app_names = self.linked_app_names(self.selected_link.linked_domain)
                app_name = app_names.get(detail.app_id, detail.app_id)
            return '{} ({})'.format(name, app_name)

        if record.model == MODEL_FIXTURE:
            detail = record.wrapped_detail
            tag = gettext_lazy('Unknown')
            if detail:
                domain_name = self.selected_link.linked_domain
                if LookupTable.objects.domain_tag_exists(domain_name, detail.tag):
                    tag = detail.tag
            return '{} ({})'.format(name, tag)

        if record.model == MODEL_REPORT:
            detail = record.wrapped_detail
            report_name = gettext_lazy('Unknown Report')
            if detail:
                try:
                    report_name = ReportConfiguration.get(detail.report_id).title
                except ResourceNotFound:
                    pass
            return '{} ({})'.format(name, report_name)

        if record.model == MODEL_KEYWORD:
            detail = record.wrapped_detail
            keyword_name = gettext_lazy('Unknown Keyword')
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
            DataTablesColumn(gettext('Link')),
            DataTablesColumn(gettext('Date ({})'.format(tzname))),
            DataTablesColumn(gettext('Data Model')),
            DataTablesColumn(gettext('User')),
        ]

        return DataTablesHeader(*columns)
