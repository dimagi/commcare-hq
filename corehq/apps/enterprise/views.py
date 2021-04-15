import json
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.expressions import RawSQL
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy
from django.views import View
from django.views.decorators.http import require_POST

from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege
from djng.views.mixins import JSONResponseMixin, allow_remote_invocation
from memoized import memoized

from couchexport.export import Format
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import always_allow_project_access
from corehq.apps.accounting.models import (
    CustomerBillingRecord,
    CustomerInvoice,
)
from corehq.apps.accounting.utils import (
    get_customer_cards,
    log_accounting_error,
    quantize_accounting_decimal,
)
from corehq.apps.accounting.utils.subscription import get_account_or_404
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.util import is_linked_app
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
)
from corehq.apps.domain.views import (
    BaseAdminProjectSettingsView,
    BaseDomainView,
    DomainAccountingSettings,
    DomainViewMixin,
)
from corehq.apps.domain.views.accounting import (
    PAYMENT_ERROR_MESSAGES,
    BillingStatementPdfView,
    BulkStripePaymentView,
    InvoiceStripePaymentView,
    WireInvoiceView,
)
from corehq.apps.enterprise.decorators import require_enterprise_admin
from corehq.apps.enterprise.enterprise import EnterpriseReport
from corehq.apps.enterprise.forms import EnterpriseSettingsForm
from corehq.apps.enterprise.tasks import email_enterprise_report
from corehq.apps.export.utils import get_default_export_settings_if_available
from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_type_by_tag,
    get_fixture_data_types,
)
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import pretty_doc_info
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.linked_domain.const import (
    LINKED_MODELS,
    LINKED_MODELS_MAP,
    MODEL_APP,
    MODEL_CASE_SEARCH,
    MODEL_DATA_DICTIONARY,
    MODEL_DIALER_SETTINGS,
    MODEL_FIXTURE,
    MODEL_HMAC_CALLOUT_SETTINGS,
    MODEL_KEYWORD,
    MODEL_OTP_SETTINGS,
    MODEL_REPORT,
)
from corehq.apps.linked_domain.dbaccessors import (
    get_domain_master_link,
    get_linked_domains,
)
from corehq.apps.linked_domain.exceptions import (
    DomainLinkError,
    UnsupportedActionError,
)
from corehq.apps.linked_domain.models import (
    AppLinkDetail,
    DomainLink,
    DomainLinkHistory,
    FixtureLinkDetail,
    KeywordLinkDetail,
    ReportLinkDetail,
    wrap_detail,
)
from corehq.apps.linked_domain.tasks import push_models
from corehq.apps.linked_domain.updates import update_model_type
from corehq.apps.linked_domain.util import server_to_user_time
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import DomainReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.sms.models import Keyword
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain
from corehq.apps.userreports.models import ReportConfiguration
from corehq.const import USER_DATE_FORMAT
from corehq.util.timezones.utils import get_timezone_for_request


@always_allow_project_access
@login_and_domain_required
def enterprise_dashboard(request, domain):
    account = get_account_or_404(request, domain)

    if not has_privilege(request, privileges.PROJECT_ACCESS):
        return HttpResponseRedirect(reverse(EnterpriseBillingStatementsView.urlname, args=(domain,)))

    context = {
        'account': account,
        'domain': domain,
        'reports': [EnterpriseReport.create(slug, account.id, request.couch_user) for slug in (
            EnterpriseReport.DOMAINS,
            EnterpriseReport.WEB_USERS,
            EnterpriseReport.MOBILE_USERS,
            EnterpriseReport.FORM_SUBMISSIONS,
        )],
        'current_page': {
            'page_name': _('Enterprise Dashboard'),
            'title': _('Enterprise Dashboard'),
        }
    }
    return render(request, "enterprise/enterprise_dashboard.html", context)


@login_and_domain_required
def enterprise_dashboard_total(request, domain, slug):
    account = get_account_or_404(request, domain)
    report = EnterpriseReport.create(slug, account.id, request.couch_user)
    return JsonResponse({'total': report.total})


@login_and_domain_required
def enterprise_dashboard_download(request, domain, slug, export_hash):
    account = get_account_or_404(request, domain)
    report = EnterpriseReport.create(slug, account.id, request.couch_user)

    redis = get_redis_client()
    content = redis.get(export_hash)

    if content:
        file = ContentFile(content)
        response = HttpResponse(file, Format.FORMAT_DICT[Format.UNZIPPED_CSV])
        response['Content-Length'] = file.size
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(report.filename)
        return response

    return HttpResponseNotFound(_("That report was not found. Please remember that "
                                  "download links expire after 24 hours."))


@login_and_domain_required
def enterprise_dashboard_email(request, domain, slug):
    account = get_account_or_404(request, domain)
    report = EnterpriseReport.create(slug, account.id, request.couch_user)
    email_enterprise_report.delay(domain, slug, request.couch_user)
    message = _("Generating {title} report, will email to {email} when complete.").format(**{
        'title': report.title,
        'email': request.couch_user.username,
    })
    return JsonResponse({'message': message})


@login_and_domain_required
def enterprise_settings(request, domain):
    account = get_account_or_404(request, domain)
    export_settings = get_default_export_settings_if_available(domain)

    if request.method == 'POST':
        form = EnterpriseSettingsForm(request.POST, domain=domain, account=account,
                                      username=request.user.username, export_settings=export_settings)
    else:
        form = EnterpriseSettingsForm(domain=domain, account=account, username=request.user.username,
                                      export_settings=export_settings)

    context = {
        'account': account,
        'accounts_email': settings.ACCOUNTS_EMAIL,
        'domain': domain,
        'restrict_signup': request.POST.get('restrict_signup', account.restrict_signup),
        'current_page': {
            'title': _('Enterprise Settings'),
            'page_name': _('Enterprise Settings'),
        },
        'settings_form': form,
    }
    return render(request, "enterprise/enterprise_settings.html", context)


@login_and_domain_required
@require_POST
def edit_enterprise_settings(request, domain):
    account = get_account_or_404(request, domain)
    export_settings = get_default_export_settings_if_available(domain)
    form = EnterpriseSettingsForm(request.POST, username=request.user.username, domain=domain,
                                  account=account, export_settings=export_settings)

    if form.is_valid():
        form.save(account)
        messages.success(request, "Account successfully updated.")
    else:
        return enterprise_settings(request, domain)

    return HttpResponseRedirect(reverse('enterprise_settings', args=[domain]))


@method_decorator(require_enterprise_admin, name='dispatch')
class BaseEnterpriseAdminView(BaseDomainView):
    section_name = ugettext_lazy("Enterprise Dashboard")

    @property
    def section_url(self):
        return reverse('enterprise_dashboard', args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))


class EnterpriseBillingStatementsView(DomainAccountingSettings, CRUDPaginatedViewMixin):
    template_name = 'domain/billing_statements.html'
    urlname = 'enterprise_billing_statements'
    page_title = ugettext_lazy("Billing Statements")

    limit_text = ugettext_lazy("statements per page")
    empty_notification = ugettext_lazy("No Billing Statements match the current criteria.")
    loading_message = ugettext_lazy("Loading statements...")

    @property
    def stripe_cards(self):
        return get_customer_cards(self.request.user.username, self.domain)

    @property
    def show_hidden(self):
        if not self.request.user.is_superuser:
            return False
        return bool(self.request.POST.get('additionalData[show_hidden]'))

    @property
    def show_unpaid(self):
        try:
            return json.loads(self.request.POST.get('additionalData[show_unpaid]'))
        except TypeError:
            return False

    @property
    def invoices(self):
        account = self.account or get_account_or_404(self.request, self.request.domain)
        invoices = CustomerInvoice.objects.filter(account=account)
        if not self.show_hidden:
            invoices = invoices.filter(is_hidden=False)
        if self.show_unpaid:
            invoices = invoices.filter(date_paid__exact=None)
        return invoices.order_by('-date_start', '-date_end')

    @property
    def total(self):
        return self.paginated_invoices.count

    @property
    @memoized
    def paginated_invoices(self):
        return Paginator(self.invoices, self.limit)

    @property
    def total_balance(self):
        """
        Returns the total balance of unpaid, unhidden invoices.
        Doesn't take into account the view settings on the page.
        """
        account = self.account or get_account_or_404(self.request, self.request.domain)
        invoices = (CustomerInvoice.objects
                    .filter(account=account)
                    .filter(date_paid__exact=None)
                    .filter(is_hidden=False))
        return invoices.aggregate(
            total_balance=Sum('balance')
        ).get('total_balance') or 0.00

    @property
    def column_names(self):
        return [
            _("Statement No."),
            _("Billing Period"),
            _("Date Due"),
            _("Payment Status"),
            _("PDF"),
        ]

    @property
    def page_context(self):
        pagination_context = self.pagination_context
        pagination_context.update({
            'stripe_options': {
                'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                'stripe_cards': self.stripe_cards,
            },
            'payment_error_messages': PAYMENT_ERROR_MESSAGES,
            'payment_urls': {
                'process_invoice_payment_url': reverse(
                    InvoiceStripePaymentView.urlname,
                    args=[self.domain],
                ),
                'process_bulk_payment_url': reverse(
                    BulkStripePaymentView.urlname,
                    args=[self.domain],
                ),
                'process_wire_invoice_url': reverse(
                    WireInvoiceView.urlname,
                    args=[self.domain],
                ),
            },
            'total_balance': self.total_balance,
            'show_plan': False
        })
        return pagination_context

    @property
    def can_pay_invoices(self):
        return self.request.couch_user.is_domain_admin(self.domain)

    @property
    def paginated_list(self):
        for invoice in self.paginated_invoices.page(self.page).object_list:
            try:
                last_billing_record = CustomerBillingRecord.objects.filter(
                    invoice=invoice
                ).latest('date_created')
                if invoice.is_paid:
                    payment_status = (_("Paid on %s.")
                                      % invoice.date_paid.strftime(USER_DATE_FORMAT))
                    payment_class = "label label-default"
                else:
                    payment_status = _("Not Paid")
                    payment_class = "label label-danger"
                date_due = (
                    (invoice.date_due.strftime(USER_DATE_FORMAT)
                     if not invoice.is_paid else _("Already Paid"))
                    if invoice.date_due else _("None")
                )
                yield {
                    'itemData': {
                        'id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'start': invoice.date_start.strftime(USER_DATE_FORMAT),
                        'end': invoice.date_end.strftime(USER_DATE_FORMAT),
                        'plan': None,
                        'payment_status': payment_status,
                        'payment_class': payment_class,
                        'date_due': date_due,
                        'pdfUrl': reverse(
                            BillingStatementPdfView.urlname,
                            args=[self.domain, last_billing_record.pdf_data_id]
                        ),
                        'canMakePayment': (not invoice.is_paid
                                           and self.can_pay_invoices),
                        'balance': "%s" % quantize_accounting_decimal(invoice.balance),
                    },
                    'template': 'statement-row-template',
                }
            except CustomerBillingRecord.DoesNotExist:
                log_accounting_error(
                    "An invoice was generated for %(invoice_id)d "
                    "(domain: %(domain)s), but no billing record!" % {
                        'invoice_id': invoice.id,
                        'domain': self.domain,
                    },
                    show_stack_trace=True
                )

    def refresh_item(self, item_id):
        pass

    def post(self, *args, **kwargs):
        return self.paginate_crud_response


@method_decorator(toggles.ERM_DEVELOPMENT.required_decorator(), name='dispatch')
class LinkedDomainsView(BaseAdminProjectSettingsView):
    urlname = 'linked_domains'
    page_title = ugettext_lazy("Linked Project Spaces")
    template_name = 'enterprise/linked_domains.html'

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
        (master_fixtures, linked_fixtures) = self._get_fixtures(master_link)
        (master_reports, linked_reports) = self._get_reports()
        (master_keywords, linked_keywords) = self._get_keywords()

        # Models belonging to this domain's master domain, for the purpose of pulling
        model_status = self._get_model_status(
            master_link, linked_apps, linked_fixtures, linked_reports, linked_keywords
        )

        # Models belonging to this domain, for the purpose of pushing to linked domains
        master_model_status = self._get_master_model_status(
            master_apps, master_fixtures, master_reports, master_keywords
        )

        return {
            'domain': self.domain,
            'timezone': timezone.localize(datetime.utcnow()).tzname(),
            'is_linked_domain': bool(master_link),
            'is_master_domain': bool(len(linked_domains)),
            'view_data': {
                'master_link': self._link_context(master_link, timezone) if master_link else None,
                'model_status': sorted(model_status, key=lambda m: m['name']),
                'master_model_status': sorted(master_model_status, key=lambda m: m['name']),
                'linked_domains': sorted(linked_domains, key=lambda d: d['linked_domain']),
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

    def _get_fixtures(self, master_link):
        master_list = self._get_fixtures_for_domain(self.domain)
        linked_list = self._get_fixtures_for_domain(master_link.master_domain) if master_link else {}
        return (master_list, linked_list)

    def _get_fixtures_for_domain(self, domain):
        fixtures = get_fixture_data_types(domain)
        return {f.tag: f for f in fixtures if f.is_global}

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

    def _get_keywords(self):
        master_list = {}
        linked_list = {}
        keywords = Keyword.objects.filter(domain=self.domain)
        for keyword in keywords:
            if keyword.upstream_id:
                linked_list[str(keyword.id)] = keyword
            else:
                master_list[str(keyword.id)] = keyword
        return (master_list, linked_list)

    def _link_context(self, link, timezone):
        return {
            'linked_domain': link.linked_domain,
            'master_domain': link.qualified_master,
            'remote_base_url': link.remote_base_url,
            'is_remote': link.is_remote,
            'last_update': server_to_user_time(link.last_pull, timezone) if link.last_pull else 'Never',
        }

    def _get_master_model_status(self, apps, fixtures, reports, keywords, ignore_models=None):
        model_status = []
        ignore_models = ignore_models or []

        for model, name in LINKED_MODELS:
            if (
                model not in ignore_models
                and model not in (MODEL_APP, MODEL_FIXTURE, MODEL_REPORT, MODEL_KEYWORD)
                and (model != MODEL_CASE_SEARCH or toggles.SYNC_SEARCH_CASE_CLAIM.enabled(self.domain))
                and (model != MODEL_DATA_DICTIONARY or toggles.DATA_DICTIONARY.enabled(self.domain))
                and (model != MODEL_DIALER_SETTINGS or toggles.WIDGET_DIALER.enabled(self.domain))
                and (model != MODEL_OTP_SETTINGS or toggles.GAEN_OTP_SERVER.enabled(self.domain))
                and (model != MODEL_HMAC_CALLOUT_SETTINGS or toggles.HMAC_CALLOUT.enabled(self.domain))
            ):
                model_status.append({
                    'type': model,
                    'name': name,
                    'last_update': _('Never'),
                    'detail': None,
                    'can_update': True
                })

        linked_models = dict(LINKED_MODELS)
        for app in apps.values():
            update = {
                'type': MODEL_APP,
                'name': '{} ({})'.format(linked_models['app'], app.name),
                'last_update': None,
                'detail': AppLinkDetail(app_id=app._id).to_json(),
                'can_update': True
            }
            model_status.append(update)
        for fixture in fixtures.values():
            update = {
                'type': MODEL_FIXTURE,
                'name': '{} ({})'.format(linked_models['fixture'], fixture.tag),
                'last_update': None,
                'detail': FixtureLinkDetail(tag=fixture.tag).to_json(),
                'can_update': fixture.is_global,
            }
            model_status.append(update)
        for report in reports.values():
            report = ReportConfiguration.get(report.get_id)
            update = {
                'type': MODEL_REPORT,
                'name': f"{linked_models['report']} ({report.title})",
                'last_update': None,
                'detail': ReportLinkDetail(report_id=report.get_id).to_json(),
                'can_update': True,
            }
            model_status.append(update)

        for keyword in keywords.values():
            update = {
                'type': MODEL_KEYWORD,
                'name': f"{linked_models['keyword']} ({keyword.keyword})",
                'last_update': None,
                'detail': KeywordLinkDetail(keyword_id=str(keyword.id)).to_json(),
                'can_update': True,
            }
            model_status.append(update)

        return model_status

    def _get_model_status(self, master_link, apps, fixtures, reports, keywords):
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
                app_name = _('Unknown App')
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

            if action.model == 'fixture':
                tag_name = _('Unknown Table')
                can_update = False
                if action.model_detail:
                    detail = action.wrapped_detail
                    tag = action.wrapped_detail.tag
                    fixture = fixtures.pop(tag, None)
                    if not fixture:
                        fixture = get_fixture_data_type_by_tag(self.domain, tag)
                    if fixture:
                        tag_name = fixture.tag
                        can_update = fixture.is_global
                update['name'] = f'{name} ({tag_name})'
                update['can_update'] = can_update
            if action.model == 'report':
                report_id = action.wrapped_detail.report_id
                try:
                    report = reports.get(report_id)
                    del reports[report_id]
                except KeyError:
                    report = ReportConfiguration.get(report_id)
                update['name'] = f'{name} ({report.title})'
            if action.model == 'keyword':
                keyword_id = action.wrapped_detail.linked_keyword_id
                try:
                    keyword = keywords[keyword_id].keyword
                    del keywords[keyword_id]
                except KeyError:
                    try:
                        keyword = Keyword.objects.get(id=keyword_id).keyword
                    except Keyword.DoesNotExist:
                        keyword = ugettext_lazy("Deleted Keyword")
                        update['can_update'] = False
                update['name'] = f'{name} ({keyword})'

            model_status.append(update)

        # Add in models and apps that have never been synced
        model_status.extend(
            self._get_master_model_status(
                apps, fixtures, reports, keywords, ignore_models=models_seen)
        )

        return model_status


@method_decorator(domain_admin_required, name='dispatch')
class LinkedDomainsRMIView(JSONResponseMixin, View, DomainViewMixin):
    urlname = "linked_domains_rmi"

    @allow_remote_invocation
    def update_linked_model(self, in_data):
        model = in_data['model']
        type_ = model['type']
        detail = model['detail']
        detail_obj = wrap_detail(type_, detail) if detail else None

        master_link = get_domain_master_link(self.domain)
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
            'message': _('''
                Your release has begun. You will receive an email when it is complete.
                Until then, to avoid linked domains receiving inconsistent content, please
                avoid editing any of the data contained in the release.
            '''),
        }


class LinkedDomainsHistoryReport(GenericTabularReport):
    name = 'Linked Project Space History'
    base_template = "reports/base_template.html"
    section_name = 'Project Settings'
    slug = 'linked_domains_history'
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
                    keyword_name = Keyword.objects.get(detail.keyword_id)
                except Keyword.DoesNotExist:
                    pass
            return f'{name} ({keyword_name})'

        return name

    @property
    def headers(self):
        tzname = self.timezone.localize(datetime.utcnow()).tzname()
        columns = [
            DataTablesColumn(_('Link')),
            DataTablesColumn(_('Date ({})'.format(tzname))),
            DataTablesColumn(_('Data Model')),
            DataTablesColumn(_('User')),
        ]

        return DataTablesHeader(*columns)
