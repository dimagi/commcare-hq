from corehq.apps.accounting.dispatcher import (
    AccountingAdminInterfaceDispatcher
)
from corehq.apps.accounting.filters import *
from corehq.apps.accounting.forms import AdjustBalanceForm
from corehq.apps.accounting.models import (
    BillingAccount, Subscription, SoftwarePlan
)
from corehq.apps.accounting.utils import get_money_str
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import (
    DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
)
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from corehq.apps.reports.generic import GenericTabularReport


class AddItemInterface(GenericTabularReport):
    base_template = 'accounting/add_new_item_button.html'
    exportable = True

    item_name = None
    new_item_view = None

    @property
    def template_context(self):
        context = super(AddItemInterface, self).template_context
        context.update(
            item_name=self.item_name,
            new_url_name=reverse(self.new_item_view.urlname),
        )
        return context

class AccountingInterface(AddItemInterface):
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher

    item_name = "Billing Account"

    crud_form_update_url = "/accounting/form/"

    fields = ['corehq.apps.accounting.interface.DateCreatedFilter',
              'corehq.apps.accounting.interface.NameFilter',
              'corehq.apps.accounting.interface.SalesforceAccountIDFilter',
              'corehq.apps.accounting.interface.AccountTypeFilter',
              ]
    hide_filters = False

    def validate_document_class(self):
        return True

    @property
    def new_item_view(self):
        from corehq.apps.accounting.views import NewBillingAccountView
        return NewBillingAccountView

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name"),
            DataTablesColumn("Salesforce Account ID"),
            DataTablesColumn("Date Created"),
            DataTablesColumn("Account Type"),
        )

    @property
    def rows(self):
        rows = []
        filters = {}

        if DateCreatedFilter.use_filter(self.request):
            filters.update(
                date_created__gte=DateCreatedFilter.get_start_date(self.request),
                date_created__lte=DateCreatedFilter.get_end_date(self.request),
            )
        name = NameFilter.get_value(self.request, self.domain)
        if name is not None:
            filters.update(
                name=name,
            )
        salesforce_account_id = SalesforceAccountIDFilter.get_value(self.request, self.domain)
        if salesforce_account_id is not None:
            filters.update(
                salesforce_account_id=salesforce_account_id,
            )
        account_type = AccountTypeFilter.get_value(self.request, self.domain)
        if account_type is not None:
            filters.update(
                account_type=account_type,
            )

        for account in BillingAccount.objects.filter(**filters):
            rows.append([mark_safe('<a href="./%d">%s</a>' % (account.id, account.name)),
                         account.salesforce_account_id,
                         account.date_created.date(),
                         account.account_type])
        return rows

    @property
    def report_context(self):
        context = super(AccountingInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context

    name = "Billing Accounts"
    description = "List of all billing accounts"
    slug = "accounts"

    crud_item_type = "Billing Account"


class SubscriptionInterface(AddItemInterface):
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher

    item_name = "Subscription"

    crud_form_update_url = "/accounting/form/"

    fields = ['corehq.apps.accounting.interface.StartDateFilter',
              'corehq.apps.accounting.interface.EndDateFilter',
              'corehq.apps.accounting.interface.DateCreatedFilter',
              'corehq.apps.accounting.interface.SubscriberFilter',
              'corehq.apps.accounting.interface.SalesforceContractIDFilter',
              'corehq.apps.accounting.interface.ActiveStatusFilter',
              'corehq.apps.accounting.interface.DoNotInvoiceFilter',
              ]
    hide_filters = False

    def validate_document_class(self):
        return True

    @property
    def new_item_view(self):
        from corehq.apps.accounting.views import NewSubscriptionViewNoDefaultDomain
        return NewSubscriptionViewNoDefaultDomain

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Subscriber"),
            DataTablesColumn("Account"),
            DataTablesColumn("Plan"),
            DataTablesColumn("Active"),
            DataTablesColumn("Salesforce Contract ID"),
            DataTablesColumn("Start Date"),
            DataTablesColumn("End Date"),
            DataTablesColumn("Do Not Invoice"),
            DataTablesColumn("Action"),
        )

    @property
    def rows(self):
        from corehq.apps.accounting.views import ManageBillingAccountView
        rows = []
        filters = {}

        if StartDateFilter.use_filter(self.request):
            filters.update(
                date_start__gte=StartDateFilter.get_start_date(self.request),
                date_start__lte=StartDateFilter.get_end_date(self.request),
            )
        if EndDateFilter.use_filter(self.request):
            filters.update(
                date_end__gte=EndDateFilter.get_start_date(self.request),
                date_end__lte=EndDateFilter.get_end_date(self.request),
            )
        if DateCreatedFilter.use_filter(self.request):
            filters.update(
                date_created__gte=DateCreatedFilter.get_start_date(self.request),
                date_created__lte=DateCreatedFilter.get_end_date(self.request),
            )
        subscriber = SubscriberFilter.get_value(self.request, self.domain)
        if subscriber is not None:
            filters.update(
                subscriber__domain=subscriber,
            )
        salesforce_contract_id = SalesforceContractIDFilter.get_value(self.request, self.domain)
        if salesforce_contract_id is not None:
            filters.update(
                salesforce_contract_id=salesforce_contract_id,
            )
        active_status = ActiveStatusFilter.get_value(self.request, self.domain)
        if active_status is not None:
            filters.update(
                is_active=(active_status == ActiveStatusFilter.active),
            )
        do_not_invoice = DoNotInvoiceFilter.get_value(self.request, self.domain)
        if do_not_invoice is not None:
            filters.update(
                do_not_invoice=(do_not_invoice == DO_NOT_INVOICE),
            )

        for subscription in Subscription.objects.filter(**filters):
            rows.append([subscription.subscriber.domain,
                         mark_safe('<a href="%s">%s</a>'
                                   % (reverse(ManageBillingAccountView.urlname, args=(subscription.account.id,)),
                                      subscription.account.name)),
                         subscription.plan_version.plan.name,
                         subscription.is_active,
                         subscription.salesforce_contract_id,
                         subscription.date_start,
                         subscription.date_end,
                         subscription.do_not_invoice,
                         mark_safe('<a href="./%d" class="btn">Edit</a>' % subscription.id)])

        return rows

    @property
    def report_context(self):
        context = super(SubscriptionInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context

    name = "Subscriptions"
    description = "List of all subscriptions"
    slug = "subscriptions"

    crud_item_type = "Subscription"


class SoftwarePlanInterface(AddItemInterface):
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher

    item_name = "Software Plan"

    crud_form_update_url = "/accounting/form/"

    fields = [
        'corehq.apps.accounting.interface.SoftwarePlanNameFilter',
        'corehq.apps.accounting.interface.SoftwarePlanEditionFilter',
        'corehq.apps.accounting.interface.SoftwarePlanVisibilityFilter',
    ]
    hide_filters = False

    def validate_document_class(self):
        return True

    @property
    def new_item_view(self):
        from corehq.apps.accounting.views import NewSoftwarePlanView
        return NewSoftwarePlanView

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name"),
            DataTablesColumn("Description"),
            DataTablesColumn("Edition"),
            DataTablesColumn("Visibility"),
            DataTablesColumn("Date of Last Version"),
        )

    @property
    def rows(self):
        rows = []
        filters = {}

        name = SoftwarePlanNameFilter.get_value(self.request, self.domain)
        if name is not None:
            filters.update(
                name=name,
            )
        edition = SoftwarePlanEditionFilter.get_value(self.request, self.domain)
        if edition is not None:
            filters.update(
                edition=edition,
            )
        visibility = SoftwarePlanVisibilityFilter.get_value(self.request, self.domain)
        if visibility is not None:
            filters.update(
                visibility=visibility,
            )

        for plan in SoftwarePlan.objects.filter(**filters):
            rows.append([
                mark_safe('<a href="./%d">%s</a>' % (plan.id, plan.name)),
                plan.description,
                plan.edition,
                plan.visibility,
                SoftwarePlan.objects.get(id=plan.id).get_version().date_created
                    if len(SoftwarePlanVersion.objects.filter(plan=plan)) != 0 else 'N/A',
            ])

        return rows

    @property
    def report_context(self):
        context = super(SoftwarePlanInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context

    name = "Software Plans"
    description = "List of all software plans"
    slug = "software_plans"

    crud_item_type = "Software_Plan"


class InvoiceInterface(GenericTabularReport):
    base_template = "accounting/invoice_list.html"
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher
    name = "Invoices"
    description = "List of all invoices"
    slug = "invoices"
    exportable = True
    fields = [
        'corehq.apps.accounting.interface.NameFilter',
        'corehq.apps.accounting.interface.SubscriberFilter',
        'corehq.apps.accounting.interface.PaymentStatusFilter',
        'corehq.apps.accounting.interface.StatementPeriodFilter',
        'corehq.apps.accounting.interface.DueDatePeriodFilter',
        'corehq.apps.accounting.interface.SalesforceAccountIDFilter',
        'corehq.apps.accounting.interface.SalesforceContractIDFilter',
        'corehq.apps.accounting.interface.SoftwarePlanNameFilter',
        'corehq.apps.accounting.interface.BillingContactFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Account Name"),
            DataTablesColumn("Project Space"),
            DataTablesColumn("Salesforce Account ID"),
            DataTablesColumn("Salesforce Contract ID"),
            DataTablesColumnGroup("Statement Period",
                                  DataTablesColumn("Start"),
                                  DataTablesColumn("End")),
            DataTablesColumn("Date Due"),
            DataTablesColumn("Amount Due"),
            DataTablesColumn("Payment Status"),
            DataTablesColumn("Action"),
            DataTablesColumn("View Invoice"),
        )

    @property
    def rows(self):
        from corehq.apps.accounting.views import InvoiceSummaryView

        return [
            [
                invoice.subscription.account.name,
                invoice.subscription.subscriber.domain,
                invoice.subscription.account.salesforce_account_id or "--",
                invoice.subscription.salesforce_contract_id or "--",
                invoice.date_start,
                invoice.date_end,
                invoice.date_due,
                get_money_str(invoice.balance),
                "Paid" if invoice.date_paid else "Not paid",
                # TODO - Create helper function for action button HTML
                mark_safe('<a data-toggle="modal"'
                          ' data-target="#adjustBalanceModal-%(invoice_id)d"'
                          ' href="#adjustBalanceModal-%(invoice_id)d"'
                          ' class="btn">'
                          'Adjust Balance</a>'
                          % {'invoice_id': invoice.id}),
                mark_safe('<a href="%s" class="btn">Go to Invoice</a>'
                          % reverse(InvoiceSummaryView.urlname,
                                    args=(invoice.id,))),

            ] for invoice in self.invoices
        ]

    @property
    @memoized
    def filters(self):
        filters = {}

        account_name = NameFilter.get_value(self.request, self.domain)
        if account_name is not None:
            filters.update(
                subscription__account__name=account_name,
            )

        subscriber_domain = \
            SubscriberFilter.get_value(self.request, self.domain)
        if subscriber_domain is not None:
            filters.update(
                subscription__subscriber__domain=subscriber_domain,
            )

        payment_status = \
            PaymentStatusFilter.get_value(self.request, self.domain)
        if payment_status is not None:
            filters.update(
                date_paid__isnull=(
                    payment_status == PaymentStatusFilter.NOT_PAID
                ),
            )

        statement_period = \
            StatementPeriodFilter.get_value(self.request, self.domain)
        if statement_period is not None:
            filters.update(
                date_start__gte=statement_period[0],
                date_start__lte=statement_period[1],
            )

        due_date_period = \
            DueDatePeriodFilter.get_value(self.request, self.domain)
        if due_date_period is not None:
            filters.update(
                date_due__gte=due_date_period[0],
                date_due__lte=due_date_period[1],
            )

        salesforce_account_id = \
            SalesforceAccountIDFilter.get_value(self.request, self.domain)
        if salesforce_account_id is not None:
            filters.update(
                subscription__account__salesforce_account_id=
                salesforce_account_id,
            )

        salesforce_contract_id = \
            SalesforceContractIDFilter.get_value(self.request, self.domain)
        if salesforce_contract_id is not None:
            filters.update(
                subscription__salesforce_contract_id=salesforce_contract_id,
            )

        plan_name = SoftwarePlanNameFilter.get_value(self.request, self.domain)
        if plan_name is not None:
            filters.update(
                subscription__plan_version__plan__name=plan_name,
            )

        contact_name = \
            BillingContactFilter.get_value(self.request, self.domain)
        if contact_name is not None:
            filters.update(
                subscription__account__in=[
                    contact_info.account.id
                    for contact_info in BillingContactInfo.objects.all()
                    if contact_name == contact_info.full_name
                ],
            )

        return filters

    @property
    @memoized
    def invoices(self):
        return Invoice.objects.filter(**self.filters)

    @property
    @memoized
    def adjust_balance_forms(self):
        return [AdjustBalanceForm(invoice) for invoice in self.invoices]

    @property
    def report_context(self):
        context = super(InvoiceInterface, self).report_context
        context.update(
            adjust_balance_forms=self.adjust_balance_forms,
        )
        return context

    @property
    @memoized
    def adjust_balance_form(self):
        return AdjustBalanceForm(
            Invoice.objects.get(id=int(self.request.POST.get('invoice_id'))),
            self.request.POST
        )

    @property
    @request_cache("default")
    def view_response(self):
        if self.request.method == 'POST':
            if self.adjust_balance_form.is_valid():
                self.adjust_balance_form.adjust_balance()
        return super(InvoiceInterface, self).view_response
