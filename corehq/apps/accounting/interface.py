import datetime

from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from couchexport.models import Format
from dimagi.utils.decorators.memoized import memoized

from corehq.const import SERVER_DATE_FORMAT
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesColumnGroup,
    DataTablesHeader,
)
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import format_datatables_data

from .dispatcher import AccountingAdminInterfaceDispatcher
from .filters import (
    AccountTypeFilter,
    ActiveStatusFilter,
    BillingContactFilter,
    CreatedSubAdjMethodFilter,
    DateCreatedFilter,
    DateFilter,
    DimagiContactFilter,
    DomainFilter,
    DoNotInvoiceFilter,
    DueDatePeriodFilter,
    EndDateFilter,
    EntryPointFilter,
    IsHiddenFilter,
    NameFilter,
    PaymentStatusFilter,
    PaymentTransactionIdFilter,
    ProBonoStatusFilter,
    SalesforceAccountIDFilter,
    SalesforceContractIDFilter,
    SoftwarePlanEditionFilter,
    SoftwarePlanNameFilter,
    SoftwarePlanVisibilityFilter,
    StartDateFilter,
    StatementPeriodFilter,
    SubscriberFilter,
    SubscriptionTypeFilter,
    TrialStatusFilter,
)
from .forms import AdjustBalanceForm
from .models import (
    BillingAccount,
    BillingContactInfo,
    CreditAdjustment,
    CreditAdjustmentReason,
    FeatureType,
    Invoice,
    PaymentRecord,
    SoftwarePlan,
    SoftwarePlanVersion,
    SoftwareProductType,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionAdjustmentReason,
    WireInvoice,
)
from .utils import (
    get_money_str,
    make_anchor_tag,
    quantize_accounting_decimal,
)


def invoice_column_cell(invoice):
    from corehq.apps.accounting.views import InvoiceSummaryView
    return format_datatables_data(
        mark_safe(make_anchor_tag(
            reverse(InvoiceSummaryView.urlname, args=(invoice.id,)),
            invoice.invoice_number
        )),
        invoice.id,
    )


class AddItemInterface(GenericTabularReport):
    base_template = 'accounting/add_new_item_button.html'
    exportable = True
    is_bootstrap3 = True

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
    name = "Billing Accounts"
    description = "List of all billing accounts"
    slug = "accounts"
    dispatcher = AccountingAdminInterfaceDispatcher

    fields = ['corehq.apps.accounting.interface.DateCreatedFilter',
              'corehq.apps.accounting.interface.NameFilter',
              'corehq.apps.accounting.interface.SalesforceAccountIDFilter',
              'corehq.apps.accounting.interface.AccountTypeFilter',
              'corehq.apps.accounting.interface.ActiveStatusFilter',
              'corehq.apps.accounting.interface.DimagiContactFilter',
              'corehq.apps.accounting.interface.EntryPointFilter',
              ]
    hide_filters = False

    item_name = "Billing Account"

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
            DataTablesColumn("Active Status"),
            DataTablesColumn("Dimagi Contact"),
            DataTablesColumn("Entry Point"),
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
        is_active = ActiveStatusFilter.get_value(self.request, self.domain)
        if is_active is not None:
            filters.update(
                is_active=is_active == ActiveStatusFilter.active,
            )
        dimagi_contact = DimagiContactFilter.get_value(self.request, self.domain)
        if dimagi_contact is not None:
            filters.update(
                dimagi_contact=dimagi_contact,
            )
        entry_point = EntryPointFilter.get_value(self.request, self.domain)
        if entry_point is not None:
            filters.update(
                entry_point=entry_point,
            )

        for account in BillingAccount.objects.filter(**filters):
            rows.append([
                mark_safe('<a href="./%d">%s</a>' % (account.id, account.name)),
                account.salesforce_account_id,
                account.date_created.date(),
                account.account_type,
                "Active" if account.is_active else "Inactive",
                account.dimagi_contact,
                account.entry_point,
            ])
        return rows

    @property
    def report_context(self):
        context = super(AccountingInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context


class SubscriptionInterface(AddItemInterface):
    section_name = "Accounting"
    name = "Subscriptions"
    description = "List of all subscriptions"
    slug = "subscriptions"
    dispatcher = AccountingAdminInterfaceDispatcher

    fields = [
        'corehq.apps.accounting.interface.StartDateFilter',
        'corehq.apps.accounting.interface.EndDateFilter',
        'corehq.apps.accounting.interface.DateCreatedFilter',
        'corehq.apps.accounting.interface.SubscriberFilter',
        'corehq.apps.accounting.interface.SalesforceContractIDFilter',
        'corehq.apps.accounting.interface.ActiveStatusFilter',
        'corehq.apps.accounting.interface.DoNotInvoiceFilter',
        'corehq.apps.accounting.interface.CreatedSubAdjMethodFilter',
        'corehq.apps.accounting.interface.TrialStatusFilter',
        'corehq.apps.accounting.interface.SubscriptionTypeFilter',
        'corehq.apps.accounting.interface.ProBonoStatusFilter',
    ]
    hide_filters = False

    item_name = "Subscription"

    def validate_document_class(self):
        return True

    @property
    def new_item_view(self):
        from corehq.apps.accounting.views import NewSubscriptionViewNoDefaultDomain
        return NewSubscriptionViewNoDefaultDomain

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn("Subscriber"),
            DataTablesColumn("Account"),
            DataTablesColumn("Plan"),
            DataTablesColumn("Active"),
            DataTablesColumn("Salesforce Contract ID"),
            DataTablesColumn("Start Date"),
            DataTablesColumn("End Date"),
            DataTablesColumn("Do Not Invoice"),
            DataTablesColumn("Created By"),
            DataTablesColumn("Type"),
            DataTablesColumn("Discounted"),
        )
        if not self.is_rendered_as_email:
            header.add_column(DataTablesColumn("Action"))
        return header

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
                do_not_invoice=(do_not_invoice == DoNotInvoiceFilter.DO_NOT_INVOICE),
            )

        filter_created_by = CreatedSubAdjMethodFilter.get_value(
            self.request, self.domain)
        if (filter_created_by is not None and filter_created_by in
            [s[0] for s in SubscriptionAdjustmentMethod.CHOICES]
        ):
            filters.update({
                'subscriptionadjustment__reason': SubscriptionAdjustmentReason.CREATE,
                'subscriptionadjustment__method': filter_created_by,
            })

        trial_status_filter = TrialStatusFilter.get_value(self.request, self.domain)
        if trial_status_filter is not None:
            is_trial = trial_status_filter == TrialStatusFilter.TRIAL
            filters.update(is_trial=is_trial)

        service_type = SubscriptionTypeFilter.get_value(self.request, self.domain)
        if service_type is not None:
            filters.update(
                service_type=service_type,
            )

        pro_bono_status = ProBonoStatusFilter.get_value(self.request, self.domain)
        if pro_bono_status is not None:
            filters.update(
                pro_bono_status=pro_bono_status,
            )

        for subscription in Subscription.objects.filter(**filters):
            try:
                created_by_adj = SubscriptionAdjustment.objects.filter(
                    subscription=subscription,
                    reason=SubscriptionAdjustmentReason.CREATE
                ).order_by('date_created')[0]
                created_by = dict(SubscriptionAdjustmentMethod.CHOICES).get(
                    created_by_adj.method, "Unknown")
            except (IndexError, SubscriptionAdjustment.DoesNotExist) as e:
                created_by = "Unknown"
            columns = [
                subscription.subscriber.domain,
                format_datatables_data(
                    text=mark_safe('<a href="%s">%s</a>' % (
                        reverse(ManageBillingAccountView.urlname, args=(subscription.account.id,)
                        ), subscription.account.name)),
                    sort_key=subscription.account.name,
                ),
                subscription.plan_version.plan.name,
                subscription.is_active,
                subscription.salesforce_contract_id,
                subscription.date_start,
                subscription.date_end,
                subscription.do_not_invoice,
                created_by,
                subscription.service_type,
                subscription.pro_bono_status,
            ]
            if not self.is_rendered_as_email:
                columns.append(mark_safe('<a href="./%d" class="btn btn-default">Edit</a>' % subscription.id))
            rows.append(columns)

        return rows

    @property
    def report_context(self):
        context = super(SubscriptionInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context


class SoftwarePlanInterface(AddItemInterface):
    section_name = "Accounting"
    name = "Software Plans"
    description = "List of all software plans"
    slug = "software_plans"
    dispatcher = AccountingAdminInterfaceDispatcher

    fields = [
        'corehq.apps.accounting.interface.SoftwarePlanNameFilter',
        'corehq.apps.accounting.interface.SoftwarePlanEditionFilter',
        'corehq.apps.accounting.interface.SoftwarePlanVisibilityFilter',
    ]
    hide_filters = False

    item_name = "Software Plan"

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


def get_exportable_column(amount):
    return format_datatables_data(
        text=get_money_str(amount),
        sort_key=amount,
    )


def get_exportable_column_cost(subtotal, deduction):
    return format_datatables_data(
        text=get_column_formatted_str(subtotal, deduction),
        sort_key=subtotal,
    )


def get_column_formatted_str(subtotal, deduction):
    return mark_safe('%s<br />(%s)') % (
        get_money_str(subtotal),
        get_money_str(deduction)
    )


def get_subtotal_and_deduction(line_items):
    subtotal = 0
    deduction = 0
    for line_item in line_items:
        subtotal += line_item.subtotal
        deduction += line_item.applied_credit
    return subtotal, deduction


class InvoiceInterfaceBase(GenericTabularReport):
    base_template = "accounting/invoice_list.html"
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher
    exportable = True
    export_format_override = Format.CSV
    is_bootstrap3 = True


class WireInvoiceInterface(InvoiceInterfaceBase):
    name = "Wire Invoices"
    description = "List of all wire invoices"
    slug = "wire_invoices"
    fields = [
        'corehq.apps.accounting.interface.DomainFilter',
        'corehq.apps.accounting.interface.PaymentStatusFilter',
        'corehq.apps.accounting.interface.StatementPeriodFilter',
        'corehq.apps.accounting.interface.DueDatePeriodFilter',
        'corehq.apps.accounting.interface.IsHiddenFilter',
    ]

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn("Invoice #"),
            DataTablesColumn("Account Name (Fogbugz Client Name)"),
            DataTablesColumn("Project Space"),
            DataTablesColumn("New This Month?"),
            DataTablesColumn("Company Name"),
            DataTablesColumn("Emails"),
            DataTablesColumn("First Name"),
            DataTablesColumn("Last Name"),
            DataTablesColumn("Phone Number"),
            DataTablesColumn("Address Line 1"),
            DataTablesColumn("Address Line 2"),
            DataTablesColumn("City"),
            DataTablesColumn("State/Province/Region"),
            DataTablesColumn("Postal Code"),
            DataTablesColumn("Country"),
            DataTablesColumnGroup("Statement Period",
                                  DataTablesColumn("Start"),
                                  DataTablesColumn("End")),
            DataTablesColumn("Date Due"),
            DataTablesColumn("Total"),
            DataTablesColumn("Amount Due"),
            DataTablesColumn("Payment Status"),
            DataTablesColumn("Do Not Invoice"),
        )

        if not self.is_rendered_as_email:
            header.add_column(DataTablesColumn("View Invoice"))
        return header

    @property
    def rows(self):
        from corehq.apps.accounting.views import (
            WireInvoiceSummaryView, ManageBillingAccountView,
        )
        rows = []
        for invoice in self.invoices:
            new_this_month = (invoice.date_created.month == invoice.account.date_created.month
                              and invoice.date_created.year == invoice.account.date_created.year)
            try:
                contact_info = BillingContactInfo.objects.get(account=invoice.account)
            except BillingContactInfo.DoesNotExist:
                contact_info = BillingContactInfo()

            account_url = reverse(ManageBillingAccountView.urlname, args=[invoice.account.id])
            invoice_url = reverse(WireInvoiceSummaryView.urlname, args=(invoice.id,))
            columns = [
                format_datatables_data(
                    mark_safe(make_anchor_tag(invoice_url, invoice.invoice_number)),
                    invoice.id,
                ),
                format_datatables_data(
                    mark_safe(make_anchor_tag(account_url, invoice.account.name)),
                    invoice.account.name
                ),
                invoice.get_domain(),
                "YES" if new_this_month else "no",
                contact_info.company_name,
                ', '.join(contact_info.email_list),
                contact_info.first_name,
                contact_info.last_name,
                contact_info.phone_number,
                contact_info.first_line,
                contact_info.second_line,
                contact_info.city,
                contact_info.state_province_region,
                contact_info.postal_code,
                contact_info.country,
                invoice.date_start,
                invoice.date_end,
                invoice.date_due,
                get_exportable_column(invoice.subtotal),
                get_exportable_column(invoice.balance),
                "Paid" if invoice.is_paid else "Not paid",
                "YES" if invoice.is_hidden else "no",
            ]

            if not self.is_rendered_as_email:
                columns.extend([
                    mark_safe(make_anchor_tag(invoice_url, 'Go to Invoice'))
                ])
            rows.append(columns)
        return rows

    @property
    @memoized
    def filters(self):
        filters = {}

        domain_name = DomainFilter.get_value(self.request, self.domain)
        if domain_name is not None:
            filters.update(domain=domain_name)

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

        is_hidden = IsHiddenFilter.get_value(self.request, self.domain)
        if is_hidden is not None:
            filters.update(
                is_hidden=(is_hidden == IsHiddenFilter.IS_HIDDEN),
            )

        return filters

    @property
    @memoized
    def invoices(self):
        return WireInvoice.objects.filter(**self.filters)

    @property
    def email_response(self):
        self.is_rendered_as_email = True
        statement_start = StatementPeriodFilter.get_value(
            self.request, self.domain) or datetime.date.today()
        return render_to_string('accounting/bookkeeper_email.html',
            {
                'headers': self.headers,
                'month': statement_start.strftime("%B"),
                'rows': self.rows,
            }
        )


class InvoiceInterface(InvoiceInterfaceBase):
    name = "Invoices"
    description = "List of all invoices"
    slug = "invoices"
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
        'corehq.apps.accounting.interface.IsHiddenFilter',
    ]

    @property
    def headers(self):
        header = DataTablesHeader(
            DataTablesColumn("Invoice #"),
            DataTablesColumn("Account Name (Fogbugz Client Name)"),
            DataTablesColumn("Subscription"),
            DataTablesColumn("Project Space"),
            DataTablesColumn("New This Month?"),
            DataTablesColumn("Company Name"),
            DataTablesColumn("Emails"),
            DataTablesColumn("First Name"),
            DataTablesColumn("Last Name"),
            DataTablesColumn("Phone Number"),
            DataTablesColumn("Address Line 1"),
            DataTablesColumn("Address Line 2"),
            DataTablesColumn("City"),
            DataTablesColumn("State/Province/Region"),
            DataTablesColumn("Postal Code"),
            DataTablesColumn("Country"),
            DataTablesColumn("Salesforce Account ID"),
            DataTablesColumn("Salesforce Contract ID"),
            DataTablesColumnGroup("Statement Period",
                                  DataTablesColumn("Start"),
                                  DataTablesColumn("End")),
            DataTablesColumn("Date Due"),
            DataTablesColumn("Plan Cost"),
            DataTablesColumn("Plan Credits"),
            DataTablesColumn("SMS Cost"),
            DataTablesColumn("SMS Credits"),
            DataTablesColumn("User Cost"),
            DataTablesColumn("User Credits"),
            DataTablesColumn("Total"),
            DataTablesColumn("Total Credits"),
            DataTablesColumn("Amount Due"),
            DataTablesColumn("Payment Status"),
            DataTablesColumn("Do Not Invoice"),
        )

        if not self.is_rendered_as_email:
            header.add_column(DataTablesColumn("Action"))
        return header

    @property
    def rows(self):
        from corehq.apps.accounting.views import (
            InvoiceSummaryView, ManageBillingAccountView, EditSubscriptionView,
        )
        rows = []
        for invoice in self.invoices:
            new_this_month = (invoice.date_created.month == invoice.subscription.account.date_created.month
                              and invoice.date_created.year == invoice.subscription.account.date_created.year)
            try:
                contact_info = BillingContactInfo.objects.get(
                    account=invoice.subscription.account,
                )
            except BillingContactInfo.DoesNotExist:
                contact_info = BillingContactInfo()

            plan_name = u"{name} v{version}".format(
                name=invoice.subscription.plan_version.plan.name,
                version=invoice.subscription.plan_version.version,
            )
            plan_href = reverse(EditSubscriptionView.urlname, args=[invoice.subscription.id])
            account_name = invoice.subscription.account.name
            account_href = reverse(ManageBillingAccountView.urlname, args=[invoice.subscription.account.id])
            invoice_href = reverse(InvoiceSummaryView.urlname, args=(invoice.id,))

            columns = [
                invoice_column_cell(invoice),
                format_datatables_data(
                    mark_safe(make_anchor_tag(account_href, account_name)),
                    invoice.subscription.account.name
                ),
                format_datatables_data(
                    mark_safe(make_anchor_tag(plan_href, plan_name)),
                    invoice.subscription.plan_version.plan.name
                ),
                invoice.subscription.subscriber.domain,
                "YES" if new_this_month else "no",
                contact_info.company_name,
                ', '.join(contact_info.email_list),
                contact_info.first_name,
                contact_info.last_name,
                contact_info.phone_number,
                contact_info.first_line,
                contact_info.second_line,
                contact_info.city,
                contact_info.state_province_region,
                contact_info.postal_code,
                contact_info.country,
                invoice.subscription.account.salesforce_account_id or "--",
                invoice.subscription.salesforce_contract_id or "--",
                invoice.date_start,
                invoice.date_end,
                invoice.date_due if invoice.date_due else "None",
            ]

            plan_subtotal, plan_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_products().all()
            )
            sms_subtotal, sms_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_feature_by_type(FeatureType.SMS).all()
            )
            user_subtotal, user_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_feature_by_type(
                    FeatureType.USER
                ).all()
            )

            columns.extend([
                get_exportable_column(plan_subtotal),
                get_exportable_column(plan_deduction),
                get_exportable_column(sms_subtotal),
                get_exportable_column(sms_deduction),
                get_exportable_column(user_subtotal),
                get_exportable_column(user_deduction),
                get_exportable_column(invoice.subtotal),
                get_exportable_column(invoice.applied_credit),
                get_exportable_column(invoice.balance),
                "Paid" if invoice.is_paid else "Not paid",
                "YES" if invoice.is_hidden else "no",
            ])

            if not self.is_rendered_as_email:
                adjust_name = "Adjust Balance"
                adjust_href = "#adjustBalanceModal-{invoice_id}".format(invoice_id=invoice.id)
                adjust_attrs = {
                    "data-toggle": "modal",
                    "data-target": adjust_href,
                    "class": "btn btn-default",
                }
                columns.append(
                    mark_safe(make_anchor_tag(adjust_href, adjust_name, adjust_attrs)),
                )
            rows.append(columns)
        return rows

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

        is_hidden = IsHiddenFilter.get_value(self.request, self.domain)
        if is_hidden is not None:
            filters.update(
                is_hidden=(is_hidden == IsHiddenFilter.IS_HIDDEN),
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
        if self.request.GET.items():  # A performance improvement
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
    @request_cache()
    def view_response(self):
        if self.request.method == 'POST':
            if self.adjust_balance_form.is_valid():
                self.adjust_balance_form.adjust_balance(
                    web_user=self.request.user.username,
                )
        return super(InvoiceInterface, self).view_response

    @property
    def email_response(self):
        self.is_rendered_as_email = True
        statement_start = StatementPeriodFilter.get_value(
            self.request, self.domain) or datetime.date.today()
        return render_to_string('accounting/bookkeeper_email.html',
            {
                'headers': self.headers,
                'month': statement_start.strftime("%B"),
                'rows': self.rows,
            }
        )


def _get_domain_from_payment_record(payment_record):
    from corehq.apps.accounting.models import CreditAdjustment
    credit_adjustments = CreditAdjustment.objects.filter(payment_record=payment_record)
    domains = set(
        credit_adj.credit_line.account.created_by_domain
        for credit_adj in credit_adjustments
        if credit_adj.credit_line.account.created_by_domain
    ) | set(
        credit_adj.credit_line.subscription.subscriber.domain
        for credit_adj in credit_adjustments
        if credit_adj.credit_line.subscription
    )
    return ', '.join(domains) if domains else None


class PaymentRecordInterface(GenericTabularReport):
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher
    name = "Payment Records"
    description = "A list of all payment records and transaction IDs from " \
                  "Stripe."
    slug = "payment_records"
    base_template = 'accounting/report_filter_actions.html'
    asynchronous = True
    exportable = True
    is_bootstrap3 = True

    fields = [
        'corehq.apps.accounting.interface.DateCreatedFilter',
        'corehq.apps.accounting.interface.NameFilter',
        'corehq.apps.accounting.interface.SubscriberFilter',
        'corehq.apps.accounting.interface.PaymentTransactionIdFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Date Created"),
            DataTablesColumn("Account"),
            DataTablesColumn("Project"),
            DataTablesColumn("Billing Admin"),
            DataTablesColumn("Stripe Transaction ID"),
            DataTablesColumn("Amount (USD)"),
        )

    @property
    def filters(self):
        filters = {}
        account_name = NameFilter.get_value(self.request, self.domain)
        if account_name is not None:
            filters.update(
                creditadjustment__credit_line__account__name=account_name,
            )
        if DateCreatedFilter.use_filter(self.request):
            filters.update(
                date_created__gte=DateCreatedFilter.get_start_date(self.request),
                date_created__lte=DateCreatedFilter.get_end_date(self.request),
            )
        subscriber = SubscriberFilter.get_value(self.request, self.domain)
        if subscriber is not None:
            filters.update(
                creditadjustment__credit_line__subscription__subscriber__domain=subscriber
            )
        transaction_id = PaymentTransactionIdFilter.get_value(self.request, self.domain)
        if transaction_id:
            filters.update(
                transaction_id=transaction_id.strip(),
            )
        return filters

    @property
    def payment_records(self):
        return PaymentRecord.objects.filter(**self.filters)

    @property
    def rows(self):
        from corehq.apps.accounting.views import ManageBillingAccountView
        rows = []
        for record in self.payment_records:
            applicable_credit_line = CreditAdjustment.objects.filter(
                payment_record_id=record.id
            ).latest('last_modified').credit_line
            account = applicable_credit_line.account
            rows.append([
                format_datatables_data(
                    text=record.date_created.strftime(SERVER_DATE_FORMAT),
                    sort_key=record.date_created.isoformat(),
                ),
                format_datatables_data(
                    text=mark_safe(
                        make_anchor_tag(
                            reverse(ManageBillingAccountView.urlname, args=[account.id]),
                            account.name
                        )
                    ),
                    sort_key=account.name,
                ),
                _get_domain_from_payment_record(record),
                record.payment_method.web_user,
                format_datatables_data(
                    text=mark_safe(
                        '<a href="https://dashboard.stripe.com/payments/%s"'
                        '   target="_blank">%s'
                        '</a>' % (
                            record.transaction_id,
                            record.transaction_id,
                        )),
                    sort_key=record.transaction_id,
                ),
                quantize_accounting_decimal(record.amount),
            ])
        return rows


class SubscriptionAdjustmentInterface(GenericTabularReport):
    section_name = 'Accounting'
    dispatcher = AccountingAdminInterfaceDispatcher
    name = 'Subscription Adjustments'
    description = 'A log of all subscription changes.'
    slug = 'subscription_adjustments'
    base_template = 'accounting/report_filter_actions.html'
    asynchronous = True
    exportable = True
    is_bootstrap3 = True

    fields = [
        'corehq.apps.accounting.interface.DomainFilter',
        'corehq.apps.accounting.interface.DateFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Date"),
            DataTablesColumn("Subscription"),
            DataTablesColumn("Project Space"),
            DataTablesColumn("Reason"),
            DataTablesColumn("Method"),
            DataTablesColumn("Note"),
            DataTablesColumn("By User"),
        )

    @property
    def rows(self):
        from corehq.apps.accounting.views import EditSubscriptionView

        def get_choice(choice, choices):
            for slug, user_text in choices:
                if choice == slug:
                    return user_text
            return None

        return [
            map(lambda x: x or '', [
                sub_adj.date_created,
                format_datatables_data(
                    mark_safe(make_anchor_tag(
                        reverse(EditSubscriptionView.urlname, args=(sub_adj.subscription.id,)),
                        sub_adj.subscription
                    )),
                    sub_adj.subscription.id,
                ),
                sub_adj.subscription.subscriber.domain,
                get_choice(sub_adj.reason, SubscriptionAdjustmentReason.CHOICES),
                get_choice(sub_adj.method, SubscriptionAdjustmentMethod.CHOICES),
                sub_adj.note,
                sub_adj.web_user,
            ])
            for sub_adj in self.subscription_adjustments
        ]

    @property
    def subscription_adjustments(self):
        query = SubscriptionAdjustment.objects.all()

        domain = DomainFilter.get_value(self.request, self.domain)
        if domain is not None:
            query = query.filter(subscription__subscriber__domain=domain)

        if DateFilter.use_filter(self.request):
            query = query.filter(
                date_created__gte=DateFilter.get_start_date(self.request),
                date_created__lte=DateFilter.get_end_date(self.request),
            )

        return query


class CreditAdjustmentInterface(GenericTabularReport):
    section_name = 'Accounting'
    dispatcher = AccountingAdminInterfaceDispatcher
    name = 'Credit Adjustments'
    description = 'A log of all credit line changes.'
    slug = 'credit_adjustments'
    base_template = 'accounting/report_filter_actions.html'
    asynchronous = True
    exportable = True
    is_bootstrap3 = True

    fields = [
        'corehq.apps.accounting.interface.NameFilter',
        'corehq.apps.accounting.interface.DomainFilter',
        'corehq.apps.accounting.interface.DateFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Date"),
            DataTablesColumnGroup(
                "Credit Line",
                DataTablesColumn("Account"),
                DataTablesColumn("Subscription"),
                DataTablesColumn("Product/Feature Type")
            ),
            DataTablesColumn("Project Space"),
            DataTablesColumn("Reason"),
            DataTablesColumn("Invoice"),
            DataTablesColumn("Note"),
            DataTablesColumn("Amount"),
            DataTablesColumn("By User"),
            DataTablesColumnGroup(
                "Related Credit Line",
                DataTablesColumn("Account"),
                DataTablesColumn("Subscription"),
                DataTablesColumn("Product/Feature Type")
            ),
        )

    @property
    def rows(self):
        from corehq.apps.accounting.views import (
            EditSubscriptionView,
            ManageBillingAccountView,
        )

        def _get_credit_line_columns_from_credit_line(credit_line):
            return [
                format_datatables_data(
                    text=mark_safe(
                        make_anchor_tag(
                            reverse(ManageBillingAccountView.urlname, args=[credit_line.account.id]),
                            credit_line.account.name
                        )
                    ),
                    sort_key=credit_line.account.name,
                ),
                format_datatables_data(
                    mark_safe(make_anchor_tag(
                        reverse(EditSubscriptionView.urlname, args=(credit_line.subscription.id,)),
                        credit_line.subscription
                    )),
                    credit_line.subscription.id,
                ) if credit_line.subscription else '',
                dict(FeatureType.CHOICES).get(
                    credit_line.feature_type,
                    dict(SoftwareProductType.CHOICES).get(
                        credit_line.product_type,
                        "Any"
                    ),
                ),
            ]

        return [
            map(lambda x: x or '', [
                credit_adj.date_created,
            ] + _get_credit_line_columns_from_credit_line(credit_adj.credit_line) + [
                (
                    credit_adj.credit_line.subscription.subscriber.domain
                    if credit_adj.credit_line.subscription is not None else (
                        credit_adj.invoice.subscription.subscriber.domain
                        if credit_adj.invoice else ''
                    )
                ),
                dict(CreditAdjustmentReason.CHOICES)[credit_adj.reason],
                invoice_column_cell(credit_adj.invoice) if credit_adj.invoice else None,
                credit_adj.note,
                quantize_accounting_decimal(credit_adj.amount),
                credit_adj.web_user,
            ] + (
                _get_credit_line_columns_from_credit_line(credit_adj.related_credit)
                if credit_adj.related_credit else ['', '', '']
            ))
            for credit_adj in self.filtered_credit_adjustments
        ]

    @property
    def filtered_credit_adjustments(self):
        query = CreditAdjustment.objects.all()

        account_name = NameFilter.get_value(self.request, self.domain)
        if account_name is not None:
            query = query.filter(credit_line__account__name=account_name)

        domain = DomainFilter.get_value(self.request, self.domain)
        if domain is not None:
            query = query.filter(
                Q(credit_line__subscription__subscriber__domain=domain) |
                Q(invoice__subscription__subscriber__domain=domain) |
                Q(
                    credit_line__subscription__isnull=True,
                    invoice__isnull=True,
                    credit_line__account__created_by_domain=domain,
                )
            )

        if DateFilter.use_filter(self.request):
            query = query.filter(
                date_created__gte=DateFilter.get_start_date(self.request),
                date_created__lte=DateFilter.get_end_date(self.request),
            )

        return query
