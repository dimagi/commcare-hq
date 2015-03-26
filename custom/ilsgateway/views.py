import base64
import StringIO
from datetime import datetime
import json
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.http.response import HttpResponseRedirect, Http404
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import SQLProduct
from corehq.apps.domain.views import BaseDomainView, DomainViewMixin
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import SMSLog
from corehq.apps.sms.util import clean_phone_number
from corehq.apps.users.models import CommCareUser, WebUser, UserRole
from django.http import HttpResponse
from django.utils.translation import ugettext_noop
from django.views.decorators.http import require_POST
from corehq.apps.domain.decorators import domain_admin_required
from custom.ilsgateway.forms import SupervisionDocumentForm
from custom.ilsgateway.tanzania.reminders.delivery import send_delivery_reminder
from custom.ilsgateway.tanzania.reminders.randr import send_ror_reminder
from custom.ilsgateway.tanzania.reminders.stockonhand import send_soh_reminder
from custom.ilsgateway.tanzania.reminders.supervision import send_supervision_reminder

from custom.ilsgateway.tasks import ILS_FACILITIES, get_ilsgateway_data_migrations
from casexml.apps.stock.models import StockTransaction
from custom.logistics.tasks import sms_users_fix, fix_groups_in_location_task
from custom.ilsgateway.api import ILSGatewayAPI
from custom.logistics.tasks import stock_data_task
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig, ReportRun, SupervisionDocument, DeliveryGroups, ILSNotes
from custom.ilsgateway.tasks import report_run, ils_clear_stock_data_task, \
    ils_bootstrap_domain_task
from custom.logistics.views import BaseConfigView, BaseRemindersTester


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
            'inbound_messages': SMSLog.count_incoming_by_domain(self.domain),
            'outbound_messages': SMSLog.count_outgoing_by_domain(self.domain)
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


class SupervisionDocumentListView(BaseDomainView):
    section_name = 'Supervision Documents'
    section_url = ""
    template_name = "ilsgateway/supervision_docs.html"
    urlname = 'supervision'

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

    @property
    def main_context(self):
        main_context = super(SupervisionDocumentListView, self).main_context
        main_context.update({
            'form': SupervisionDocumentForm(),
            'documents': SupervisionDocument.objects.filter(domain=self.domain),
            'is_user_domain_admin': self.request.couch_user.is_domain_admin(self.domain)
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


class RemindersTester(BaseRemindersTester):
    post_url = 'ils_reminders_tester'
    template_name = 'ilsgateway/reminders_tester.html'

    reminders = {
        'delivery_reminder': send_delivery_reminder,
        'randr_reminder': send_ror_reminder,
        'soh_reminder': send_soh_reminder,
        'supervision_reminder': send_supervision_reminder
    }

    def get_context_data(self, **kwargs):
        context = super(RemindersTester, self).get_context_data(**kwargs)
        context['current_groups'] = "Submiting group: %s, Processing group: %s, Delivering group: %s" % (
            DeliveryGroups().current_submitting_group(),
            DeliveryGroups().current_processing_group(),
            DeliveryGroups().current_delivering_group(),
        )
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        reminder = request.POST.get('reminder')
        phone_number = context.get('phone_number')

        if reminder and phone_number:
            phone_number = clean_phone_number(phone_number)
            v = VerifiedNumber.by_phone(phone_number, include_pending=True)
            if v and v.verified:
                user = v.owner
                if not user:
                    return self.get(request, *args, **kwargs)
                reminder_function = self.reminders.get(reminder)
                reminder_function(self.domain, datetime.now(), test_list=[user])
        messages.success(request, "Reminder was sent successfully")
        return self.get(request, *args, **kwargs)


@domain_admin_required
@require_POST
def sync_ilsgateway(request, domain):
    ils_bootstrap_domain_task.delay(domain)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ils_sync_stock_data(request, domain):
    config = ILSGatewayConfig.for_domain(domain)
    domain = config.domain
    endpoint = ILSGatewayEndpoint.from_config(config)
    apis = get_ilsgateway_data_migrations()
    stock_data_task.delay(domain, endpoint, apis, config, ILS_FACILITIES)
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def ils_clear_stock_data(request, domain):
    ils_clear_stock_data_task.delay()
    return HttpResponse('OK')

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
        rr.save()
    except ReportRun.DoesNotExist, ReportRun.MultipleObjectsReturned:
        pass
    return HttpResponseRedirect(reverse(ILSConfigView.urlname, kwargs={'domain': domain}))


@domain_admin_required
@require_POST
def ils_sms_users_fix(request, domain):
    config = ILSGatewayConfig.for_domain(domain)
    endpoint = ILSGatewayEndpoint.from_config(config)
    sms_users_fix.delay(ILSGatewayAPI(domain=domain, endpoint=endpoint))
    return HttpResponse('OK')


@domain_admin_required
@require_POST
def delete_reports_runs(request, domain):
    runs = ReportRun.objects.filter(domain=domain)
    runs.delete()
    return HttpResponse('OK')


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
        date=datetime.now(),
        text=post_data['text']
    ).save()
    data = []
    for row in ILSNotes.objects.filter(domain=domain, location=location).order_by('date'):
        data.append([
            row.user_name,
            row.user_role,
            row.date.strftime('%Y-%m-%d %H:%M'),
            row.user_phone,
            row.text
        ])

    return HttpResponse(json.dumps(data), content_type='application/json')


@domain_admin_required
@require_POST
def fix_groups_in_location(request, domain):
    fix_groups_in_location_task.delay(domain)
    return HttpResponse('OK')
