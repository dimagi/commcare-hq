import base64
import StringIO
from datetime import datetime
import json
from django.core.urlresolvers import reverse, reverse_lazy
from django.db.models import Count
from django.http.response import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView, RedirectView
from django.views.generic.edit import DeleteView
from django.views.generic.list import ListView
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import SQLProduct
from corehq.apps.domain.views import BaseDomainView, DomainViewMixin
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.models import SMS, INCOMING, OUTGOING
from corehq.apps.style.decorators import use_datatables
from corehq.apps.users.models import CommCareUser, WebUser, UserRole
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq.apps.domain.decorators import domain_admin_required, login_and_domain_required
from corehq.const import SERVER_DATETIME_FORMAT_NO_SEC
from custom.ilsgateway import DashboardReport
from custom.ilsgateway.forms import SupervisionDocumentForm
from custom.ilsgateway.oneoff import recalculate_moshi_rural_task, recalculate_non_facilities_task
from custom.ilsgateway.tanzania import make_url
from custom.ilsgateway.tanzania.reports.delivery import DeliveryReport
from custom.ilsgateway.tanzania.reports.randr import RRreport
from custom.ilsgateway.tanzania.reports.stock_on_hand import StockOnHandReport
from custom.ilsgateway.tanzania.reports.supervision import SupervisionReport
from casexml.apps.stock.models import StockTransaction
from custom.ilsgateway.models import ILSGatewayConfig, ReportRun, SupervisionDocument, ILSNotes, \
    PendingReportingDataRecalculation, OneOffTaskProgress
from custom.ilsgateway.tasks import report_run
from custom.logistics.views import BaseConfigView


class GlobalStats(BaseDomainView):
    section_name = 'Global Stats'
    section_url = ""
    template_name = "ilsgateway/global_stats.html"
    show_supply_point_types = False
    root_name = 'MOHSW'

    @property
    def main_context(self):
        contacts = CommCareUser.by_domain(self.domain, reduce=True)
        web_users = WebUser.by_domain(self.domain)
        web_users_admins = web_users_read_only = 0
        facilities = SQLLocation.objects.filter(domain=self.domain, location_type__name__iexact='FACILITY')
        admin_role_list = UserRole.by_domain_and_name(self.domain, 'Administrator')
        if admin_role_list:
            admin_role = admin_role_list[0]
        else:
            admin_role = None
        for web_user in web_users:
            dm = web_user.get_domain_membership(self.domain)
            if admin_role and dm.role_id == admin_role.get_id:
                web_users_admins += 1
            else:
                web_users_read_only += 1

        main_context = super(GlobalStats, self).main_context
        entities_reported_stock = SQLLocation.objects.filter(
            domain=self.domain,
            location_type__administrative=False
        ).count()

        context = {
            'root_name': self.root_name,
            'country': SQLLocation.objects.filter(domain=self.domain,
                                                  location_type__name__iexact=self.root_name).count(),
            'region': SQLLocation.objects.filter(domain=self.domain, location_type__name__iexact='region').count(),
            'district': SQLLocation.objects.filter(
                domain=self.domain,
                location_type__name__iexact='district'
            ).count(),
            'entities_reported_stock': entities_reported_stock,
            'facilities': len(facilities),
            'contacts': contacts[0]['value'] if contacts else 0,
            'web_users': len(web_users),
            'web_users_admins': web_users_admins,
            'web_users_read_only': web_users_read_only,
            'products': SQLProduct.objects.filter(domain=self.domain, is_archived=False).count(),
            'product_stocks': StockState.objects.filter(sql_product__domain=self.domain).count(),
            'stock_transactions': StockTransaction.objects.filter(report__domain=self.domain).count(),
            'inbound_messages': SMS.count_by_domain(self.domain, direction=INCOMING),
            'outbound_messages': SMS.count_by_domain(self.domain, direction=OUTGOING),
        }

        if self.show_supply_point_types:
            counts = SQLLocation.objects.values('location_type__name').filter(domain=self.domain).annotate(
                Count('location_type')
            ).order_by('location_type__name')
            context['location_types'] = counts
        main_context.update(context)
        return main_context


class ILSConfigView(BaseConfigView):
    config = ILSGatewayConfig
    urlname = 'ils_config'
    sync_urlname = 'sync_ilsgateway'
    sync_stock_url = 'ils_sync_stock_data'
    clear_stock_url = 'ils_clear_stock_data'
    page_title = ugettext_noop("ILSGateway")
    template_name = 'ilsgateway/ilsconfig.html'
    source = 'ilsgateway'

    @property
    def page_context(self):
        context = super(ILSConfigView, self).page_context
        context['oneoff_tasks'] = OneOffTaskProgress.objects.filter(domain=self.domain)
        return context


class SupervisionDocumentListView(BaseDomainView):
    section_name = 'Supervision Documents'
    section_url = ""
    template_name = "ilsgateway/supervision_docs.html"
    urlname = 'supervision'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.is_web_user():
            raise Http404()
        return super(SupervisionDocumentListView, self).dispatch(request, *args, **kwargs)

    @method_decorator(domain_admin_required)
    def post(self, *args, **kwargs):
        request = args[0]
        form = SupervisionDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            supervision_document = SupervisionDocument(
                name=form.cleaned_data['document'].name,
                document=base64.b64encode(form.cleaned_data['document'].read()),
                data_type=form.cleaned_data['document'].content_type,
                domain=self.domain
            )
            supervision_document.save()
        return HttpResponseRedirect(
            reverse(self.urlname, args=[self.domain])
        )

    def _ils_make_url(self, cls):
        params = '?location_id=%s&filter_by_program=%s&datespan_type=%s&datespan_first=%s&datespan_second=%s'
        return make_url(cls, self.domain, params, (
            self.request.GET.get(
                'location_id', get_object_or_404(
                    SQLLocation, domain=self.domain, location_type__name='MOHSW'
                ).location_id
            ),
            self.request.GET.get('filter_by_program', ''),
            self.request.GET.get('datespan_type', ''),
            self.request.GET.get('datespan_first', ''),
            self.request.GET.get('datespan_second', ''),
        ))

    @property
    def report_links(self):
        return [
            ('Dashboard Report', self._ils_make_url(DashboardReport)),
            ('Stock On Hand', self._ils_make_url(StockOnHandReport)),
            ('R&R', self._ils_make_url(RRreport)),
            ('Delivery', self._ils_make_url(DeliveryReport)),
            ('Supervision', self._ils_make_url(SupervisionReport))
        ]

    @property
    def main_context(self):
        main_context = super(SupervisionDocumentListView, self).main_context
        main_context.update({
            'form': SupervisionDocumentForm(),
            'documents': SupervisionDocument.objects.filter(domain=self.domain),
            'is_user_domain_admin': self.request.couch_user.is_domain_admin(self.domain),
            'report_links': self.report_links
        })
        return main_context


class SupervisionDocumentView(TemplateView):

    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.is_web_user():
            raise Http404()
        return super(SupervisionDocumentView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        document_id = kwargs.get('document_id')
        try:
            document = SupervisionDocument.objects.get(pk=document_id)
        except SupervisionDocument.DoesNotExist:
            raise Http404()
        response = HttpResponse(StringIO.StringIO(base64.b64decode(document.document)))
        response['Content-Type'] = document.data_type
        response['Content-Disposition'] = 'attachment; filename=%s' % document.name
        return response


class SupervisionDocumentDeleteView(TemplateView, DomainViewMixin):

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(SupervisionDocumentDeleteView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        document_id = kwargs.get('document_id')
        try:
            document = SupervisionDocument.objects.get(pk=document_id)
        except SupervisionDocument.DoesNotExist:
            raise Http404()
        document.delete()
        return HttpResponseRedirect(
            reverse(SupervisionDocumentListView.urlname, args=[self.domain])
        )


@domain_admin_required
@require_POST
def run_warehouse_runner(request, domain):
    report_run.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def end_report_run(request, domain):
    try:
        rr = ReportRun.objects.get(domain=domain, complete=False)
        rr.complete = True
        rr.has_error = True
        rr.save()
    except ReportRun.DoesNotExist, ReportRun.MultipleObjectsReturned:
        pass
    return HttpResponseRedirect(reverse(ILSConfigView.urlname, kwargs={'domain': domain}))


@require_POST
def save_ils_note(request, domain):
    post_data = request.POST
    user = request.couch_user
    location = SQLLocation.objects.get(id=int(post_data['location']))
    ILSNotes(
        location=location,
        domain=domain,
        user_name=user.username,
        user_role=user.user_data['role'] if 'role' in user.user_data else '',
        user_phone=user.default_phone_number,
        date=datetime.utcnow(),
        text=post_data['text']
    ).save()
    data = []
    for row in ILSNotes.objects.filter(domain=domain, location=location).order_by('date'):
        data.append([
            row.user_name,
            row.user_role,
            row.date.strftime(SERVER_DATETIME_FORMAT_NO_SEC),
            row.user_phone,
            row.text
        ])

    return HttpResponse(json.dumps(data), content_type='application/json')


class ReportRunListView(ListView, DomainViewMixin):
    context_object_name = 'runs'
    template_name = 'ilsgateway/report_run_list.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.is_domain_admin():
            raise Http404()
        return super(ReportRunListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ReportRun.objects.filter(domain=self.domain).order_by('pk')


class PendingRecalculationsListView(ListView, DomainViewMixin):
    context_object_name = 'recalculations'
    template_name = 'ilsgateway/pending_recalculations.html'

    @use_datatables
    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.is_domain_admin():
            raise Http404()
        return super(PendingRecalculationsListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return PendingReportingDataRecalculation.objects.filter(domain=self.domain).order_by('pk')


class ReportRunDeleteView(DeleteView, DomainViewMixin):
    model = ReportRun
    template_name = 'ilsgateway/confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.couch_user.is_domain_admin():
            raise Http404()
        return super(ReportRunDeleteView, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('report_run_list', args=[self.domain])


class DashboardPageRedirect(RedirectView):

    def get_redirect_url(self, *args, **kwargs):
        domain = kwargs['domain']
        user = self.request.couch_user
        dm = user.get_domain_membership(domain)
        url = DashboardReport.get_url(domain)

        if dm:
            loc_id = dm.location_id
            url = '%s?location_id=%s&filter_by_program=all' % (
                url,
                loc_id or ''
            )

        return url


@domain_admin_required
@require_POST
def recalculate_moshi_rural(request, domain):
    recalculate_moshi_rural_task.delay()
    return HttpResponse('')


@domain_admin_required
@require_POST
def recalculate_non_facilities(request, domain):
    recalculate_non_facilities_task.delay(domain)
    return HttpResponse('')
