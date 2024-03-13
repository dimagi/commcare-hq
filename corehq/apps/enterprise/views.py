import json

from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import (
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_POST

from django_prbac.utils import has_privilege
from memoized import memoized

from corehq.apps.accounting.decorators import always_allow_project_access
from corehq.apps.enterprise.decorators import require_enterprise_admin
from corehq.apps.enterprise.mixins import ManageMobileWorkersMixin
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.enterprise.tasks import clear_enterprise_permissions_cache_for_all_users
from couchexport.export import Format
from dimagi.utils.couch.cache.cache_core import get_redis_client

from corehq import privileges
from corehq.apps.accounting.models import (
    CustomerInvoice,
    CustomerBillingRecord,
)
from corehq.apps.accounting.utils.stripe import get_customer_cards
from corehq.apps.accounting.utils import quantize_accounting_decimal, log_accounting_error
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    require_superuser,
)
from corehq.apps.domain.views import DomainAccountingSettings, BaseDomainView
from corehq.apps.domain.views.accounting import PAYMENT_ERROR_MESSAGES, InvoiceStripePaymentView, \
    BulkStripePaymentView, WireInvoiceView, BillingStatementPdfView

from corehq.apps.enterprise.enterprise import EnterpriseReport

from corehq.apps.enterprise.forms import EnterpriseSettingsForm
from corehq.apps.enterprise.tasks import email_enterprise_report

from corehq.apps.export.utils import get_default_export_settings_if_available

from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.users.decorators import require_can_edit_or_view_web_users

from corehq.const import USER_DATE_FORMAT


@always_allow_project_access
@require_enterprise_admin
@login_and_domain_required
def enterprise_dashboard(request, domain):
    if not has_privilege(request, privileges.PROJECT_ACCESS):
        return HttpResponseRedirect(reverse(EnterpriseBillingStatementsView.urlname, args=(domain,)))

    context = {
        'account': request.account,
        'domain': domain,
        'reports': [EnterpriseReport.create(slug, request.account.id, request.couch_user) for slug in (
            EnterpriseReport.DOMAINS,
            EnterpriseReport.WEB_USERS,
            EnterpriseReport.MOBILE_USERS,
            EnterpriseReport.FORM_SUBMISSIONS,
            EnterpriseReport.ODATA_FEEDS,
        )],
        'current_page': {
            'page_name': _('Enterprise Dashboard'),
            'title': _('Enterprise Dashboard'),
        }
    }
    return render(request, "enterprise/enterprise_dashboard.html", context)


@require_enterprise_admin
@login_and_domain_required
def enterprise_dashboard_total(request, domain, slug):
    report = EnterpriseReport.create(slug, request.account.id, request.couch_user)
    return JsonResponse({'total': report.total})


@require_enterprise_admin
@login_and_domain_required
def enterprise_dashboard_download(request, domain, slug, export_hash):
    report = EnterpriseReport.create(slug, request.account.id, request.couch_user)

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


@require_enterprise_admin
@login_and_domain_required
def enterprise_dashboard_email(request, domain, slug):
    report = EnterpriseReport.create(slug, request.account.id, request.couch_user)
    email_enterprise_report.delay(domain, slug, request.couch_user)
    message = _("Generating {title} report, will email to {email} when complete.").format(**{
        'title': report.title,
        'email': request.couch_user.username,
    })
    return JsonResponse({'message': message})


@require_enterprise_admin
@login_and_domain_required
def enterprise_settings(request, domain):
    export_settings = get_default_export_settings_if_available(domain)

    if request.method == 'POST':
        form = EnterpriseSettingsForm(request.POST, domain=domain, account=request.account,
                                      username=request.user.username, export_settings=export_settings)
    else:
        form = EnterpriseSettingsForm(domain=domain, account=request.account, username=request.user.username,
                                      export_settings=export_settings)

    context = {
        'account': request.account,
        'accounts_email': settings.ACCOUNTS_EMAIL,
        'domain': domain,
        'restrict_signup': request.POST.get('restrict_signup', request.account.restrict_signup),
        'current_page': {
            'title': _('Enterprise Settings'),
            'page_name': _('Enterprise Settings'),
        },
        'settings_form': form,
    }
    return render(request, "enterprise/enterprise_settings.html", context)


@require_enterprise_admin
@login_and_domain_required
@require_POST
def edit_enterprise_settings(request, domain):
    export_settings = get_default_export_settings_if_available(domain)
    form = EnterpriseSettingsForm(request.POST, username=request.user.username,
                                  domain=domain,
                                  account=request.account, export_settings=export_settings)

    if form.is_valid():
        form.save(request.account)
        messages.success(request, "Account successfully updated.")
    else:
        return enterprise_settings(request, domain)

    return HttpResponseRedirect(reverse('enterprise_settings', args=[domain]))


@method_decorator(require_enterprise_admin, name='dispatch')
class BaseEnterpriseAdminView(BaseDomainView):
    section_name = gettext_lazy("Enterprise Console")

    @property
    def section_url(self):
        return reverse('enterprise_dashboard', args=(self.domain,))

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain,))


@method_decorator(require_enterprise_admin, name='dispatch')
class EnterpriseBillingStatementsView(DomainAccountingSettings, CRUDPaginatedViewMixin):
    template_name = 'domain/billing_statements.html'
    urlname = 'enterprise_billing_statements'
    page_title = gettext_lazy("Billing Statements")

    limit_text = gettext_lazy("statements per page")
    empty_notification = gettext_lazy("No Billing Statements match the current criteria.")
    loading_message = gettext_lazy("Loading statements...")

    @property
    def stripe_cards(self):
        return get_customer_cards(self.request.user.username)

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
        invoices = CustomerInvoice.objects.filter(account=self.request.account)
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
        invoices = (CustomerInvoice.objects
                    .filter(account=self.request.account)
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


# This view, and related views, require enterprise admin permissions to be consistent
# with other views in this area. They also require superuser access because these views
# used to be in another part of HQ, where they were limited to superusers, and we don't
# want them to be visible to any external users until we're ready to GA this feature.
@require_can_edit_or_view_web_users
@require_superuser
@require_enterprise_admin
def enterprise_permissions(request, domain):
    config = EnterprisePermissions.get_by_domain(domain)
    if not config.id:
        config.save()
    all_domains = set(config.account.get_domains())
    ignored_domains = all_domains - set(config.domains) - {config.source_domain}

    context = {
        'domain': domain,
        'all_domains': sorted(all_domains),
        'is_enabled': config.is_enabled,
        'source_domain': config.source_domain,
        'ignored_domains': sorted(list(ignored_domains)),
        'controlled_domains': sorted(config.domains),
        'current_page': {
            'page_name': _('Enterprise Permissions'),
            'title': _('Enterprise Permissions'),
        }
    }
    return render(request, "enterprise/enterprise_permissions.html", context)


@require_superuser
@require_enterprise_admin
@require_POST
def disable_enterprise_permissions(request, domain):
    config = EnterprisePermissions.get_by_domain(domain)
    config.is_enabled = False
    config.source_domain = None
    config.save()
    clear_enterprise_permissions_cache_for_all_users.delay(config.id)

    redirect = reverse("enterprise_permissions", args=[domain])
    messages.success(request, _('Enterprise permissions have been disabled.'))
    return HttpResponseRedirect(redirect)


@require_superuser
@require_enterprise_admin
@require_POST
def add_enterprise_permissions_domain(request, domain, target_domain):
    config = EnterprisePermissions.get_by_domain(domain)

    redirect = reverse("enterprise_permissions", args=[domain])
    if target_domain not in config.account.get_domains():
        messages.error(request, _("Could not add {}.").format(target_domain))
        return HttpResponseRedirect(redirect)

    if target_domain not in config.domains:
        config.domains.append(target_domain)
        config.save()
        if config.source_domain:
            clear_enterprise_permissions_cache_for_all_users.delay(config.id, config.source_domain)

    messages.success(request, _('{} is now included in enterprise permissions.').format(target_domain))

    return HttpResponseRedirect(redirect)


@require_superuser
@require_enterprise_admin
@require_POST
def remove_enterprise_permissions_domain(request, domain, target_domain):
    config = EnterprisePermissions.get_by_domain(domain)

    redirect = reverse("enterprise_permissions", args=[domain])
    if target_domain not in config.account.get_domains() or target_domain not in config.domains:
        messages.error(request, _("Could not remove {}.").format(target_domain))
        return HttpResponseRedirect(redirect)

    if target_domain in config.domains:
        config.domains.remove(target_domain)
        config.save()
        if config.source_domain:
            clear_enterprise_permissions_cache_for_all_users.delay(config.id, config.source_domain)
    messages.success(request, _('{} is now excluded from enterprise permissions.').format(target_domain))
    return HttpResponseRedirect(redirect)


@require_superuser
@require_enterprise_admin
@require_POST
def update_enterprise_permissions_source_domain(request, domain):
    source_domain = request.POST.get('source_domain')
    redirect = reverse("enterprise_permissions", args=[domain])

    config = EnterprisePermissions.get_by_domain(domain)
    if source_domain not in config.account.get_domains():
        messages.error(request, _("Please select a project."))
        return HttpResponseRedirect(redirect)

    config.is_enabled = True
    old_domain = config.source_domain
    config.source_domain = source_domain
    if source_domain in config.domains:
        config.domains.remove(source_domain)
    config.save()
    clear_enterprise_permissions_cache_for_all_users.delay(config.id, config.source_domain)
    clear_enterprise_permissions_cache_for_all_users.delay(config.id, old_domain)
    messages.success(request, _('Controlling domain set to {}.').format(source_domain))
    return HttpResponseRedirect(redirect)


class ManageEnterpriseMobileWorkersView(ManageMobileWorkersMixin, BaseEnterpriseAdminView):
    page_title = gettext_lazy("Manage Mobile Workers")
    template_name = 'enterprise/manage_mobile_workers.html'
    urlname = 'enterprise_manage_mobile_workers'
