import datetime
import json
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, validate_slug
from django.db import transaction
from django.forms.utils import ErrorList
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.dates import MONTHS
from django.utils.safestring import mark_safe
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.helper import FormHelper
from dateutil.relativedelta import relativedelta
from django_countries.data import COUNTRIES
from django_prbac.models import Grant, Role, UserRole
from memoized import memoized

from corehq import privileges
from corehq.apps.accounting.async_handlers import (
    FeatureRateAsyncHandler,
    SoftwareProductRateAsyncHandler,
)
from corehq.apps.accounting.exceptions import (
    CreateAccountingAdminError,
    InvoiceError,
)
from corehq.apps.accounting.invoicing import (
    CustomerAccountInvoiceFactory,
    DomainInvoiceFactory,
)
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingContactInfo,
    BillingRecord,
    CreditAdjustment,
    CreditAdjustmentReason,
    CreditLine,
    Currency,
    CustomerBillingRecord,
    CustomerInvoice,
    DefaultProductPlan,
    EntryPoint,
    Feature,
    FeatureRate,
    FeatureType,
    FundingSource,
    Invoice,
    InvoicingPlan,
    LastPayment,
    PreOrPostPay,
    ProBonoStatus,
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    SoftwarePlanVisibility,
    SoftwareProductRate,
    Subscription,
    SubscriptionType,
    WireBillingRecord,
    DomainUserHistory,
)
from corehq.apps.accounting.tasks import send_subscription_reminder_emails
from corehq.apps.accounting.utils import (
    get_account_name_from_default_name,
    get_money_str,
    has_subscription_already_ended,
    make_anchor_tag,
)
from corehq.apps.accounting.utils.software_plans import (
    upgrade_subscriptions_to_latest_plan_version,
)
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser
from corehq.util.dates import get_first_last_days


class BillingAccountBasicForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label=gettext_lazy("Salesforce Account ID"),
                                            max_length=80,
                                            required=False)
    currency = forms.ChoiceField(label="Currency")

    email_list = forms.CharField(
        label=gettext_lazy('Client Contact Emails'),
        widget=forms.SelectMultiple(choices=[]),
    )
    is_active = forms.BooleanField(
        label=gettext_lazy("Account is Active"),
        required=False,
        initial=True,
    )
    is_customer_billing_account = forms.BooleanField(
        label=gettext_lazy("Is Customer Billing Account"),
        required=False,
        initial=False
    )
    is_sms_billable_report_visible = forms.BooleanField(
        label="",
        required=False,
        initial=False
    )
    enterprise_admin_emails = forms.CharField(
        label="Enterprise Admin Emails",
        required=False,
        widget=forms.SelectMultiple(choices=[]),
    )
    enterprise_restricted_signup_domains = forms.CharField(
        label="Enterprise Domains for Restricting Signups",
        required=False,
        help_text='ex: dimagi.com, commcarehq.org',
    )
    invoicing_plan = forms.ChoiceField(
        label="Invoicing Plan",
        required=False
    )
    active_accounts = forms.IntegerField(
        label=gettext_lazy("Transfer Subscriptions To"),
        help_text=gettext_lazy(
            "Transfer any existing subscriptions to the "
            "Billing Account specified here."
        ),
        required=False,
    )
    dimagi_contact = forms.EmailField(
        label=gettext_lazy("Dimagi Contact Email"),
        max_length=BillingAccount._meta.get_field('dimagi_contact').max_length,
        required=False,
    )
    entry_point = forms.ChoiceField(
        label=gettext_lazy("Entry Point"),
        choices=EntryPoint.CHOICES,
    )
    last_payment_method = forms.ChoiceField(
        label=gettext_lazy("Last Payment Method"),
        choices=LastPayment.CHOICES
    )
    pre_or_post_pay = forms.ChoiceField(
        label=gettext_lazy("Prepay or Postpay"),
        choices=PreOrPostPay.CHOICES
    )
    account_basic = forms.CharField(widget=forms.HiddenInput, required=False)
    block_hubspot_data_for_all_users = forms.BooleanField(
        label="Enable Block Hubspot Data",
        required=False,
        initial=False,
        help_text="Users in any projects connected to this account will not "
                  "have data sent to Hubspot",
    )
    bill_web_user = forms.BooleanField(
        label="Bill Web User",
        required=False,
        initial=False,
        help_text="Include Web Users in invoice (requires a subscription with Web User Feature)"
    )

    def __init__(self, account, *args, **kwargs):
        self.account = account
        if account is not None:
            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            kwargs['initial'] = {
                'name': account.name,
                'salesforce_account_id': account.salesforce_account_id,
                'currency': account.currency.code,
                'email_list': contact_info.email_list,
                'is_active': account.is_active,
                'is_customer_billing_account': account.is_customer_billing_account,
                'is_sms_billable_report_visible': account.is_sms_billable_report_visible,
                'enterprise_admin_emails': account.enterprise_admin_emails,
                'enterprise_restricted_signup_domains': ','.join(account.enterprise_restricted_signup_domains),
                'invoicing_plan': account.invoicing_plan,
                'dimagi_contact': account.dimagi_contact,
                'entry_point': account.entry_point,
                'last_payment_method': account.last_payment_method,
                'pre_or_post_pay': account.pre_or_post_pay,
                'block_hubspot_data_for_all_users': account.block_hubspot_data_for_all_users,
                'bill_web_user': account.bill_web_user,
            }
        else:
            kwargs['initial'] = {
                'currency': Currency.get_default().code,
                'entry_point': EntryPoint.CONTRACTED,
                'last_payment_method': LastPayment.NONE,
                'pre_or_post_pay': PreOrPostPay.POSTPAY,
                'invoicing_plan': InvoicingPlan.MONTHLY
            }
        super(BillingAccountBasicForm, self).__init__(*args, **kwargs)
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
        self.fields['invoicing_plan'].choices = InvoicingPlan.CHOICES
        self.helper = FormHelper()
        self.helper.form_id = "account-form"
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        additional_fields = []
        if account is not None:
            additional_fields.append(hqcrispy.B3MultiField(
                "Active Status",
                hqcrispy.MultiInlineField(
                    'is_active',
                    data_bind="checked: is_active",
                ),
            ))
            additional_fields.append(hqcrispy.B3MultiField(
                "Customer Billing Account",
                hqcrispy.MultiInlineField(
                    'is_customer_billing_account',
                    data_bind="checked: is_customer_billing_account",
                ),
            ))
            additional_fields.append(
                crispy.Div(
                    'invoicing_plan',
                    crispy.Field(
                        'enterprise_admin_emails',
                        css_class='input-xxlarge accounting-email-select2',
                        data_initial=json.dumps(self.initial.get('enterprise_admin_emails')),
                    ),
                    data_bind='visible: is_customer_billing_account',
                    data_initial=json.dumps(self.initial.get('enterprise_admin_emails')),
                )
            )
            additional_fields.append(
                hqcrispy.B3MultiField(
                    "SMS Billable Report Visible",
                    hqcrispy.MultiInlineField(
                        'is_sms_billable_report_visible',
                        data_bind="checked: is_sms_billable_report_visible",
                    ),
                    data_bind='visible: is_customer_billing_account',
                ),
            )
            additional_fields.append(
                crispy.Div(
                    crispy.Field(
                        'enterprise_restricted_signup_domains',
                        css_class='input-xxlarge',
                    ),
                    data_bind='visible: is_customer_billing_account'
                ),
            )
            if account.subscription_set.count() > 0:
                additional_fields.append(crispy.Div(
                    crispy.Field(
                        'active_accounts',
                        css_class="input-xxlarge accounting-async-select2",
                        placeholder="Select Active Account",
                    ),
                    data_bind="visible: showActiveAccounts"
                ))
            additional_fields.extend([
                hqcrispy.B3MultiField(
                    "Block Hubspot Data for All Users",
                    hqcrispy.MultiInlineField(
                        'block_hubspot_data_for_all_users',
                    ),
                ),
                hqcrispy.B3MultiField(
                    "Bill Web Users",
                    hqcrispy.MultiInlineField('bill_web_user'),
                ),
            ])
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Basic Information',
                'name',
                crispy.Field('email_list', css_class='input-xxlarge accounting-email-select2',
                             data_initial=json.dumps(self.initial.get('email_list'))),
                crispy.Div(
                    crispy.Div(
                        css_class='col-sm-3 col-md-2'
                    ),
                    crispy.Div(
                        crispy.HTML(", ".join(self.initial.get('email_list'))),
                        css_class='col-sm-9 col-md-8 col-lg-6'
                    ),
                    css_id='emails-text',
                    css_class='collapse form-group'
                ) if self.initial.get('email_list') else crispy.Div(),
                crispy.Div(
                    crispy.Div(
                        css_class='col-sm-3 col-md-2'
                    ),
                    crispy.Div(
                        StrictButton(
                            "Show contact emails as text",
                            type="button",
                            css_class='btn btn-default',
                            css_id='show_emails'
                        ),
                        crispy.HTML('<p class="help-block">Useful when you want to copy contact emails</p>'),
                        css_class='col-sm-9 col-md-8 col-lg-6'
                    ),
                    css_class='form-group'
                ) if self.initial.get('email_list') else crispy.Div(),
                'dimagi_contact',
                'salesforce_account_id',
                'currency',
                'entry_point',
                'last_payment_method',
                'pre_or_post_pay',
                'account_basic',
                crispy.Div(*additional_fields),
            ),
            hqcrispy.FormActions(
                crispy.Submit(
                    'account_basic',
                    'Update Basic Information'
                    if account is not None else 'Add New Account',
                    css_class='disable-on-submit',
                )
            )
        )

    def clean_name(self):
        name = self.cleaned_data['name']
        conflicting_named_accounts = BillingAccount.objects.filter(name=name)
        if self.account:
            conflicting_named_accounts = conflicting_named_accounts.exclude(name=self.account.name)

        if conflicting_named_accounts.exists():
            raise ValidationError(_("Name '%s' is already taken.") % name)
        return name

    def clean_email_list(self):
        return self.data.getlist('email_list')

    def clean_enterprise_admin_emails(self):
        return self.data.getlist('enterprise_admin_emails')

    def clean_enterprise_restricted_signup_domains(self):
        if self.cleaned_data['enterprise_restricted_signup_domains']:
            # Check that no other account has claimed these domains, or we won't know which message to display
            errors = []
            accounts = BillingAccount.get_enterprise_restricted_signup_accounts()
            domains = [e.strip() for e in self.cleaned_data['enterprise_restricted_signup_domains'].split(r',')]
            for domain in domains:
                for account in accounts:
                    if domain in account.enterprise_restricted_signup_domains and account.id != self.account.id:
                        errors.append("{} is restricted by {}".format(domain, account.name))
            if errors:
                raise ValidationError("The following domains are already restricted by another account: "
                                      + ", ".join(errors))
            return domains
        else:
            # Do not return a list with an empty string
            return []

    def clean_active_accounts(self):
        transfer_subs = self.cleaned_data['active_accounts']
        if (
            not self.cleaned_data['is_active'] and self.account is not None
            and self.account.subscription_set.count() > 0
            and not transfer_subs
        ):
            raise ValidationError(
                _("This account has subscriptions associated with it. "
                  "Please specify a transfer account before deactivating.")
            )
        if self.account is not None and transfer_subs == self.account.id:
            raise ValidationError(
                _("The transfer account can't be the same one you're trying "
                  "to deactivate.")
            )
        return transfer_subs

    @transaction.atomic
    def create_account(self):
        name = self.cleaned_data['name']
        salesforce_account_id = self.cleaned_data['salesforce_account_id']
        currency, _ = Currency.objects.get_or_create(
            code=self.cleaned_data['currency']
        )
        account = BillingAccount(
            name=get_account_name_from_default_name(name),
            salesforce_account_id=salesforce_account_id,
            currency=currency,
            entry_point=self.cleaned_data['entry_point'],
            last_payment_method=self.cleaned_data['last_payment_method'],
            pre_or_post_pay=self.cleaned_data['pre_or_post_pay']
        )
        account.save()

        contact_info, _ = BillingContactInfo.objects.get_or_create(
            account=account,
        )
        contact_info.email_list = self.cleaned_data['email_list']
        contact_info.save()

        return account

    @transaction.atomic
    def update_basic_info(self, account):
        account.name = self.cleaned_data['name']
        account.is_active = self.cleaned_data['is_active']
        account.is_customer_billing_account = self.cleaned_data['is_customer_billing_account']
        account.is_sms_billable_report_visible = self.cleaned_data['is_sms_billable_report_visible']
        account.enterprise_admin_emails = self.cleaned_data['enterprise_admin_emails']
        account.enterprise_restricted_signup_domains = self.cleaned_data['enterprise_restricted_signup_domains']
        account.invoicing_plan = self.cleaned_data['invoicing_plan']
        account.block_hubspot_data_for_all_users = self.cleaned_data['block_hubspot_data_for_all_users']
        account.bill_web_user = self.cleaned_data['bill_web_user']
        transfer_id = self.cleaned_data['active_accounts']
        if transfer_id:
            transfer_account = BillingAccount.objects.get(id=transfer_id)
            for sub in account.subscription_set.all():
                sub.account = transfer_account
                sub.save()
        account.salesforce_account_id = \
            self.cleaned_data['salesforce_account_id']
        account.currency, _ = Currency.objects.get_or_create(
            code=self.cleaned_data['currency'],
        )
        account.dimagi_contact = self.cleaned_data['dimagi_contact']
        account.entry_point = self.cleaned_data['entry_point']
        account.last_payment_method = self.cleaned_data['last_payment_method']
        account.pre_or_post_pay = self.cleaned_data['pre_or_post_pay']
        account.save()

        contact_info, _ = BillingContactInfo.objects.get_or_create(
            account=account,
        )
        contact_info.email_list = self.cleaned_data['email_list']
        contact_info.save()


class BillingAccountContactForm(forms.ModelForm):

    account_contact = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta(object):
        model = BillingContactInfo
        fields = [
            'first_name',
            'last_name',
            'company_name',
            'phone_number',
            'first_line',
            'second_line',
            'city',
            'state_province_region',
            'postal_code',
            'country',
        ]
        widgets = {'country': forms.Select(choices=[])}

    def __init__(self, account, *args, **kwargs):
        contact_info, _ = BillingContactInfo.objects.get_or_create(
            account=account,
        )
        super(BillingAccountContactForm, self).__init__(instance=contact_info,
                                                        *args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        country_code = args[0].get('country') if len(args) > 0 else account.billingcontactinfo.country
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Contact Information',
                'first_name',
                'last_name',
                'company_name',
                'phone_number',
                'first_line',
                'second_line',
                'city',
                'state_province_region',
                'postal_code',
                crispy.Field(
                    'country',
                    css_class="input-xlarge accounting-country-select2",
                    data_country_code=country_code or '',
                    data_country_name=COUNTRIES.get(country_code, ''),
                ),
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'account_contact',
                        'Update Contact Information'
                    )
                )
            ),
        )


class SubscriptionForm(forms.Form):
    account = forms.IntegerField(
        label=gettext_lazy("Billing Account"),
        widget=forms.Select(choices=[]),
    )
    start_date = forms.DateField(
        label=gettext_lazy("Start Date"), widget=forms.DateInput()
    )
    end_date = forms.DateField(
        label=gettext_lazy("End Date"), widget=forms.DateInput(), required=False
    )
    plan_edition = forms.ChoiceField(
        label=gettext_lazy("Edition"), initial=SoftwarePlanEdition.ENTERPRISE,
        choices=SoftwarePlanEdition.CHOICES,
    )
    plan_visibility = forms.ChoiceField(
        label=gettext_lazy("Visibility"), initial=SoftwarePlanVisibility.PUBLIC,
        choices=SoftwarePlanVisibility.CHOICES,
    )
    most_recent_version = forms.ChoiceField(
        label=gettext_lazy("Version"), initial="True",
        choices=(("True", "Show Most Recent Version"), ("False", "Show All Versions"))
    )
    plan_version = forms.IntegerField(
        label=gettext_lazy("Software Plan"),
        widget=forms.Select(choices=[]),
    )
    domain = forms.CharField(
        label=gettext_lazy("Project Space"),
        widget=forms.Select(choices=[]),
    )
    salesforce_contract_id = forms.CharField(
        label=gettext_lazy("Salesforce Deployment ID"), max_length=80, required=False
    )
    do_not_invoice = forms.BooleanField(
        label=gettext_lazy("Do Not Invoice"), required=False
    )
    no_invoice_reason = forms.CharField(
        label=gettext_lazy("Justify why \"Do Not Invoice\""), max_length=256, required=False
    )
    do_not_email_invoice = forms.BooleanField(label="Do Not Email Invoices", required=False)
    do_not_email_reminder = forms.BooleanField(label="Do Not Email Subscription Reminders", required=False)
    auto_generate_credits = forms.BooleanField(
        label=gettext_lazy("Auto-generate Plan Credits"), required=False
    )
    skip_invoicing_if_no_feature_charges = forms.BooleanField(
        label=gettext_lazy("Skip invoicing if no feature charges"), required=False
    )
    active_accounts = forms.IntegerField(
        label=gettext_lazy("Transfer Subscription To"),
        required=False,
        widget=forms.Select(choices=[]),
    )
    service_type = forms.ChoiceField(
        label=gettext_lazy("Type"),
        choices=SubscriptionType.CHOICES,
        initial=SubscriptionType.IMPLEMENTATION,
    )
    pro_bono_status = forms.ChoiceField(
        label=gettext_lazy("Discounted"),
        choices=ProBonoStatus.CHOICES,
        initial=ProBonoStatus.NO,
    )
    funding_source = forms.ChoiceField(
        label=gettext_lazy("Funding Source"),
        choices=FundingSource.CHOICES,
        initial=FundingSource.CLIENT,
    )
    skip_auto_downgrade = forms.BooleanField(
        label=gettext_lazy("Exclude from automated downgrade process"),
        required=False
    )
    skip_auto_downgrade_reason = forms.CharField(
        label=gettext_lazy("Justify why \"Skip Auto Downgrade\""),
        max_length=256,
        required=False,
    )
    set_subscription = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, subscription, account_id, web_user, *args, **kwargs):
        # account_id is not referenced if subscription is not None
        super(SubscriptionForm, self).__init__(*args, **kwargs)
        self.subscription = subscription
        is_existing = subscription is not None
        self.web_user = web_user
        today = datetime.date.today()

        start_date_field = crispy.Field('start_date', css_class="date-picker")
        end_date_field = crispy.Field('end_date', css_class="date-picker")

        if is_existing:
            # circular import
            from corehq.apps.accounting.views import (
                SoftwarePlanVersionView, ManageBillingAccountView
            )
            from corehq.apps.domain.views.settings import DefaultProjectSettingsView
            self.fields['account'].initial = subscription.account.id
            account_field = hqcrispy.B3TextField(
                'account',
                format_html('<a href="{}">{}</a>',
                    reverse(ManageBillingAccountView.urlname, args=[subscription.account.id]),
                    subscription.account.name)
            )

            self.fields['plan_version'].initial = subscription.plan_version.id
            plan_version_field = hqcrispy.B3TextField(
                'plan_version',
                format_html('<a href="{}">{}</a>',
                    reverse(SoftwarePlanVersionView.urlname,
                        args=[subscription.plan_version.plan.id, subscription.plan_version_id]),
                    subscription.plan_version)
            )
            self.fields['plan_edition'].initial = subscription.plan_version.plan.edition
            plan_edition_field = hqcrispy.B3TextField(
                'plan_edition',
                self.fields['plan_edition'].initial
            )
            self.fields['plan_visibility'].initial = subscription.plan_version.plan.visibility
            plan_visibility_field = hqcrispy.B3TextField(
                'plan_visibility',
                self.fields['plan_visibility'].initial
            )
            is_most_recent_version = subscription.plan_version.plan.get_version() == subscription.plan_version
            most_recent_version_text = ("is most recent version" if is_most_recent_version
                                        else "not most recent version")
            self.fields['most_recent_version'].initial = is_most_recent_version
            most_recent_version_field = hqcrispy.B3TextField(
                'most_recent_version',
                most_recent_version_text
            )
            self.fields['domain'].choices = [
                (subscription.subscriber.domain, subscription.subscriber.domain)
            ]
            self.fields['domain'].initial = subscription.subscriber.domain

            domain_field = hqcrispy.B3TextField(
                'domain',
                format_html('<a href="{}">{}</a>',
                    reverse(DefaultProjectSettingsView.urlname, args=[subscription.subscriber.domain]),
                    subscription.subscriber.domain)
            )

            self.fields['start_date'].initial = subscription.date_start.isoformat()
            self.fields['end_date'].initial = (
                subscription.date_end.isoformat()
                if subscription.date_end is not None else subscription.date_end
            )
            self.fields['domain'].initial = subscription.subscriber.domain
            self.fields['salesforce_contract_id'].initial = subscription.salesforce_contract_id
            self.fields['do_not_invoice'].initial = subscription.do_not_invoice
            self.fields['no_invoice_reason'].initial = subscription.no_invoice_reason
            self.fields['do_not_email_invoice'].initial = subscription.do_not_email_invoice
            self.fields['do_not_email_reminder'].initial = subscription.do_not_email_reminder
            self.fields['auto_generate_credits'].initial = subscription.auto_generate_credits
            self.fields['skip_invoicing_if_no_feature_charges'].initial = \
                subscription.skip_invoicing_if_no_feature_charges
            self.fields['service_type'].initial = subscription.service_type
            self.fields['pro_bono_status'].initial = subscription.pro_bono_status
            self.fields['funding_source'].initial = subscription.funding_source
            self.fields['skip_auto_downgrade'].initial = subscription.skip_auto_downgrade
            self.fields['skip_auto_downgrade_reason'].initial = subscription.skip_auto_downgrade_reason

            if (
                subscription.date_start is not None
                and subscription.date_start <= today
            ):
                self.fields['start_date'].help_text = '(already started)'
            if has_subscription_already_ended(subscription):
                self.fields['end_date'].help_text = '(already ended)'

            self.fields['plan_version'].required = False
            self.fields['domain'].required = False

        else:
            account_field = crispy.Field(
                'account', css_class="input-xxlarge",
                placeholder="Search for Billing Account"
            )
            if account_id is not None:
                self.fields['account'].initial = account_id

            domain_field = crispy.Field(
                'domain', css_class="input-xxlarge",
                placeholder="Search for Project Space"
            )
            plan_edition_field = crispy.Field('plan_edition')
            plan_visibility_field = crispy.Field('plan_visibility')
            most_recent_version_field = crispy.Field('most_recent_version')
            plan_version_field = crispy.Field(
                'plan_version', css_class="input-xxlarge",
                placeholder="Search for Software Plan"
            )

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_text_inline = True
        transfer_fields = []
        if is_existing:
            transfer_fields.extend([
                crispy.Field(
                    'active_accounts',
                    css_class='input-xxlarge accounting-async-select2',
                    placeholder="Select Active Account",
                    style="width: 100%;",
                ),
            ])
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '%s Subscription' % ('Edit' if is_existing else 'New'),
                account_field,
                crispy.Div(*transfer_fields),
                start_date_field,
                end_date_field,
                crispy.Div(
                    crispy.HTML('<h4 style="margin-bottom: 20px;">%s</h4>'
                            % _("Software Plan"),),
                    plan_edition_field,
                    plan_visibility_field,
                    most_recent_version_field,
                    plan_version_field,
                    css_class="well",
                ),
                domain_field,
                'salesforce_contract_id',
                hqcrispy.B3MultiField(
                    "Invoice Options",
                    crispy.Field('do_not_invoice', data_bind="checked: noInvoice"),
                    'skip_invoicing_if_no_feature_charges',
                ),
                crispy.Div(
                    crispy.Field(
                        'no_invoice_reason', data_bind="attr: {required: noInvoice}"),
                    data_bind="visible: noInvoice"),
                hqcrispy.B3MultiField("Email Options", 'do_not_email_invoice', 'do_not_email_reminder'),
                hqcrispy.B3MultiField("Credit Options", 'auto_generate_credits'),
                'service_type',
                'pro_bono_status',
                'funding_source',
                hqcrispy.B3MultiField(
                    "Skip Auto Downgrade",
                    crispy.Field('skip_auto_downgrade', data_bind="checked: skipAutoDowngrade")
                ),
                crispy.Div(
                    crispy.Field(
                        'skip_auto_downgrade_reason', data_bind="attr: {required: skipAutoDowngrade}"
                    ),
                    data_bind="visible: skipAutoDowngrade",
                ),
                'set_subscription'
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'set_subscription',
                        '%s Subscription' % ('Update' if is_existing else 'Create'),
                        css_class='disable-on-submit',
                    )
                )
            )
        )

    @transaction.atomic
    def create_subscription(self):
        account = BillingAccount.objects.get(id=self.cleaned_data['account'])
        domain = self.cleaned_data['domain']
        plan_version = SoftwarePlanVersion.objects.get(id=self.cleaned_data['plan_version'])
        sub = Subscription.new_domain_subscription(
            account, domain, plan_version,
            web_user=self.web_user,
            internal_change=True,
            **self.shared_keywords
        )
        return sub

    @transaction.atomic
    def update_subscription(self):
        self.subscription.update_subscription(
            web_user=self.web_user,
            **self.shared_keywords
        )
        transfer_account = self.cleaned_data.get('active_accounts')
        if transfer_account:
            acct = BillingAccount.objects.get(id=transfer_account)
            CreditLine.objects.filter(
                account=self.subscription.account,  # TODO - add this constraint to postgres
                subscription=self.subscription,
            ).update(account=acct)
            self.subscription.account = acct
            self.subscription.save()

    @property
    def shared_keywords(self):
        return dict(
            date_start=self.cleaned_data['start_date'],
            date_end=self.cleaned_data['end_date'],
            do_not_invoice=self.cleaned_data['do_not_invoice'],
            no_invoice_reason=self.cleaned_data['no_invoice_reason'],
            do_not_email_invoice=self.cleaned_data['do_not_email_invoice'],
            do_not_email_reminder=self.cleaned_data['do_not_email_reminder'],
            auto_generate_credits=self.cleaned_data['auto_generate_credits'],
            skip_invoicing_if_no_feature_charges=self.cleaned_data['skip_invoicing_if_no_feature_charges'],
            salesforce_contract_id=self.cleaned_data['salesforce_contract_id'],
            service_type=self.cleaned_data['service_type'],
            pro_bono_status=self.cleaned_data['pro_bono_status'],
            funding_source=self.cleaned_data['funding_source'],
            skip_auto_downgrade=self.cleaned_data['skip_auto_downgrade'],
            skip_auto_downgrade_reason=self.cleaned_data['skip_auto_downgrade_reason'],
        )

    def clean_active_accounts(self):
        transfer_account = self.cleaned_data.get('active_accounts')
        if transfer_account and transfer_account == self.subscription.account.id:
            raise ValidationError(_("Please select an account other than the "
                                    "current account to transfer to."))
        if transfer_account:
            acct = BillingAccount.objects.get(id=transfer_account)
            if acct.is_customer_billing_account != self.subscription.plan_version.plan.is_customer_software_plan:
                if acct.is_customer_billing_account:
                    raise ValidationError("Please select a regular Billing Account to transfer to.")
                else:
                    raise ValidationError("Please select a Customer Billing Account to transfer to.")
        return transfer_account

    def clean_domain(self):
        domain = self.cleaned_data['domain']
        if self.fields['domain'].required:
            domain_obj = Domain.get_by_name(domain)
            if domain_obj is None:
                raise forms.ValidationError(_("A valid project space is required."))
        return domain

    def clean(self):
        if not self.cleaned_data.get('active_accounts') and not self.cleaned_data.get('account'):
            raise ValidationError(_("Account must be specified"))

        account_id = self.cleaned_data.get('active_accounts') or self.cleaned_data.get('account')
        if account_id:
            account = BillingAccount.objects.get(id=account_id)
            if (
                not self.cleaned_data['do_not_invoice']
                and (
                    not BillingContactInfo.objects.filter(account=account).exists()
                    or not account.billingcontactinfo.email_list
                )
            ):
                from corehq.apps.accounting.views import ManageBillingAccountView
                raise forms.ValidationError(format_html(_(
                    "Please update 'Client Contact Emails' "
                    '<strong><a href={link} target="_blank">here</a></strong> '
                    "before using Billing Account <strong>{account}</strong>."
                ),
                    link=reverse(ManageBillingAccountView.urlname, args=[account.id]),
                    account=account.name,
                ))

        start_date = self.cleaned_data.get('start_date')
        if not start_date:
            if self.subscription:
                start_date = self.subscription.date_start
            else:
                raise ValidationError(_("You must specify a start date"))

        end_date = self.cleaned_data.get('end_date')
        if end_date:
            if start_date > end_date:
                raise ValidationError(_("End date must be after start date."))

        return self.cleaned_data


class ChangeSubscriptionForm(forms.Form):
    subscription_change_note = forms.CharField(
        label=gettext_lazy("Note"),
        required=True,
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    )
    new_plan_edition = forms.ChoiceField(
        label=gettext_lazy("Edition"), initial=SoftwarePlanEdition.ENTERPRISE,
        choices=SoftwarePlanEdition.CHOICES,
    )
    new_plan_visibility = forms.ChoiceField(
        label=gettext_lazy("Visibility"), initial=SoftwarePlanVisibility.PUBLIC,
        choices=SoftwarePlanVisibility.CHOICES,
    )
    new_plan_most_recent_version = forms.ChoiceField(
        label=gettext_lazy("Version"), initial="True",
        choices=(("True", "Show Most Recent Version"), ("False", "Show All Versions"))
    )
    new_plan_version = forms.CharField(
        label=gettext_lazy("New Software Plan"),
        widget=forms.Select(choices=[]),
    )
    new_date_end = forms.DateField(
        label=gettext_lazy("End Date"), widget=forms.DateInput(), required=False
    )
    service_type = forms.ChoiceField(
        label=gettext_lazy("Type"),
        choices=SubscriptionType.CHOICES,
        initial=SubscriptionType.IMPLEMENTATION,
    )
    pro_bono_status = forms.ChoiceField(
        label=gettext_lazy("Discounted"),
        choices=ProBonoStatus.CHOICES,
        initial=ProBonoStatus.NO,
    )
    funding_source = forms.ChoiceField(
        label=gettext_lazy("Funding Source"),
        choices=FundingSource.CHOICES,
        initial=FundingSource.CLIENT,
    )

    def __init__(self, subscription, web_user, *args, **kwargs):
        self.subscription = subscription
        self.web_user = web_user
        super(ChangeSubscriptionForm, self).__init__(*args, **kwargs)

        if self.subscription.date_end is not None:
            self.fields['new_date_end'].initial = subscription.date_end

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "Change Subscription",
                crispy.Field('new_date_end', css_class="date-picker"),
                crispy.Div(
                    crispy.HTML('<h4 style="margin-bottom: 20px;">%s</h4>'
                            % _("Software Plan"),),
                    'new_plan_edition',
                    'new_plan_visibility',
                    'new_plan_most_recent_version',
                    crispy.Field(
                        'new_plan_version', css_class="input-xxlarge",
                        placeholder="Search for Software Plan",
                        style="width: 100%;"
                    ),
                    css_class="well",
                ),
                'service_type',
                'pro_bono_status',
                'funding_source',
                'subscription_change_note',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Change Subscription",
                    type="submit",
                    css_class="btn-primary disable-on-submit",
                ),
            ),
        )

    @transaction.atomic
    def change_subscription(self):
        new_plan_version = SoftwarePlanVersion.objects.get(id=self.cleaned_data['new_plan_version'])
        return self.subscription.change_plan(
            new_plan_version,
            date_end=self.cleaned_data['new_date_end'],
            web_user=self.web_user,
            service_type=self.cleaned_data['service_type'],
            pro_bono_status=self.cleaned_data['pro_bono_status'],
            funding_source=self.cleaned_data['funding_source'],
            note=self.cleaned_data['subscription_change_note'],
            internal_change=True,
        )


class BulkUpgradeToLatestVersionForm(forms.Form):
    upgrade_note = forms.CharField(
        label="Note",
        required=True,
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    )

    def __init__(self, old_plan_version, web_user, *args, **kwargs):
        self.old_plan_version = old_plan_version
        self.web_user = web_user
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "Upgrade All Subscriptions To Latest Version",
                'upgrade_note',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Upgrade All",
                    type="submit",
                    css_class="btn-primary disable-on-submit",
                ),
            ),
        )

    @transaction.atomic
    def upgrade_subscriptions(self):
        upgrade_subscriptions_to_latest_plan_version(
            self.old_plan_version,
            self.web_user,
            self.cleaned_data['upgrade_note'],
        )


class CreditForm(forms.Form):
    amount = forms.DecimalField(label="Amount (USD)")
    note = forms.CharField(required=True)
    rate_type = forms.ChoiceField(
        label=gettext_lazy("Rate Type"),
        choices=(
            ('', 'Any'),
            ('Product', 'Product'),
            ('Feature', 'Feature'),
        ),
        required=False,
    )
    feature_type = forms.ChoiceField(required=False, label=gettext_lazy("Feature Type"))
    adjust = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, account, subscription, *args, **kwargs):
        self.account = account
        self.subscription = subscription
        super(CreditForm, self).__init__(*args, **kwargs)

        self.fields['feature_type'].choices = FeatureType.CHOICES

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Add Credit',
                'amount',
                'note',
                crispy.Field('rate_type', data_bind="value: rateType"),
                crispy.Div('feature_type', data_bind="visible: showFeature"),
                'adjust'
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'adjust_credit',
                        'Update Credit',
                        css_class='disable-on-submit',
                    ),
                )
            )
        )

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        field_metadata = CreditAdjustment._meta.get_field('amount')
        if amount >= 10 ** (field_metadata.max_digits - field_metadata.decimal_places):
            raise ValidationError(mark_safe(_(  # nosec: no user input
                'Amount over maximum size.  If you need support for '
                'quantities this large, please <a data-toggle="modal" '
                'data-target="#modalReportIssue" href="#modalReportIssue">'
                'Report an Issue</a>.'
            )))
        return amount

    @transaction.atomic
    def adjust_credit(self, web_user=None):
        amount = self.cleaned_data['amount']
        note = self.cleaned_data['note']
        is_product = self.cleaned_data['rate_type'] == 'Product'
        feature_type = (self.cleaned_data['feature_type']
                        if self.cleaned_data['rate_type'] == 'Feature' else None)
        CreditLine.add_credit(
            amount,
            account=self.account,
            subscription=self.subscription,
            feature_type=feature_type,
            is_product=is_product,
            note=note,
            web_user=web_user,
            permit_inactive=True,
        )
        return True


class RemoveAutopayForm(forms.Form):

    remove_autopay = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, account, *args, **kwargs):
        super(RemoveAutopayForm, self).__init__(*args, **kwargs)
        self.account = account

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Remove Autopay User',
                'remove_autopay'
            ),
            hqcrispy.FormActions(
                StrictButton(
                    'Remove Autopay User',
                    css_class='btn-danger disable-on-submit',
                    name='cancel_subscription',
                    type='submit',
                )
            ),
        )

    def remove_autopay_user_from_account(self):
        self.account.auto_pay_user = None
        self.account.save()


class CancelForm(forms.Form):
    note = forms.CharField(
        widget=forms.TextInput,
    )
    cancel_subscription = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, subscription, *args, **kwargs):
        super(CancelForm, self).__init__(*args, **kwargs)

        can_cancel = has_subscription_already_ended(subscription)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Cancel Subscription',
                crispy.Field('note', **({'readonly': True} if can_cancel else {})),
                'cancel_subscription'
            ),
            hqcrispy.FormActions(
                StrictButton(
                    'Cancel Subscription',
                    css_class='btn-danger disable-on-submit',
                    name='cancel_subscription',
                    type='submit',
                    **({'disabled': True} if can_cancel else {})
                )
            ),
        )


class SuppressSubscriptionForm(forms.Form):
    submit_kwarg = 'suppress_subscription'
    suppress_subscription = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, subscription, *args, **kwargs):
        self.subscription = subscription
        super(SuppressSubscriptionForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form-horizontal'

        fields = [
            crispy.Div(
                crispy.HTML('Warning: this can only be undone by a developer.'),
                css_class='alert alert-danger',
            ),
            'suppress_subscription'
        ]
        if self.subscription.is_active:
            fields.append(crispy.Div(
                crispy.HTML('An active subscription cannot be suppressed.'),
                css_class='alert alert-warning',
            ))

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Suppress subscription from subscription report, invoice generation, and from being activated',
                *fields
            ),
            hqcrispy.FormActions(
                StrictButton(
                    'Suppress Subscription',
                    css_class='btn-danger disable-on-submit',
                    name=self.submit_kwarg,
                    type='submit',
                    **({'disabled': True} if self.subscription.is_active else {})
                ),
            ),
        )

    def clean(self):
        from corehq.apps.accounting.views import InvoiceSummaryView

        invoices = self.subscription.invoice_set.all()
        if invoices:
            raise ValidationError(format_html(
                "Cannot suppress subscription. Suppress these invoices first: {}",
                format_html_join(
                    ', ',
                    '<a href="{}">{}</a>',
                    [(
                        reverse(InvoiceSummaryView.urlname, args=[invoice.id]),
                        invoice.invoice_number,
                    ) for invoice in invoices])
            ))


class PlanInformationForm(forms.Form):
    name = forms.CharField(max_length=80)
    description = forms.CharField(required=False)
    edition = forms.ChoiceField(choices=SoftwarePlanEdition.CHOICES)
    visibility = forms.ChoiceField(choices=SoftwarePlanVisibility.CHOICES)
    max_domains = forms.IntegerField(required=False)
    is_customer_software_plan = forms.BooleanField(required=False)
    is_annual_plan = forms.BooleanField(required=False)

    def __init__(self, plan, *args, **kwargs):
        self.plan = plan
        if plan is not None:
            kwargs['initial'] = {
                'name': plan.name,
                'description': plan.description,
                'edition': plan.edition,
                'visibility': plan.visibility,
                'max_domains': plan.max_domains,
                'is_customer_software_plan': plan.is_customer_software_plan,
                'is_annual_plan': plan.is_annual_plan
            }
        else:
            kwargs['initial'] = {
                'edition': SoftwarePlanEdition.ENTERPRISE,
                'visibility': SoftwarePlanVisibility.INTERNAL,
            }
        super(PlanInformationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Plan Information',
                'name',
                'description',
                'edition',
                'visibility',
                'max_domains',
                'is_customer_software_plan',
                'is_annual_plan'
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'plan_information',
                        '%s Software Plan' % ('Update' if plan is not None else 'Create'),
                        css_class='disable-on-submit',
                    )
                )
            )
        )

    def clean_name(self):
        name = self.cleaned_data['name']
        if (
            len(SoftwarePlan.objects.filter(name=name)) != 0
            and (self.plan is None or self.plan.name != name)
        ):
            raise ValidationError(_('Name already taken.  Please enter a new name.'))
        return name

    def create_plan(self):
        name = self.cleaned_data['name']
        description = self.cleaned_data['description']
        edition = self.cleaned_data['edition']
        visibility = self.cleaned_data['visibility']
        max_domains = self.cleaned_data['max_domains']
        is_customer_software_plan = self.cleaned_data['is_customer_software_plan']
        is_annual_plan = self.cleaned_data['is_annual_plan']
        plan = SoftwarePlan(name=name,
                            description=description,
                            edition=edition,
                            visibility=visibility,
                            max_domains=max_domains,
                            is_customer_software_plan=is_customer_software_plan,
                            is_annual_plan=is_annual_plan
                            )
        plan.save()
        return plan

    def update_plan(self, request, plan):
        if DefaultProductPlan.objects.filter(plan=self.plan).exists():
            messages.warning(request, "You cannot modify a non-custom software plan.")
        else:
            plan.name = self.cleaned_data['name']
            plan.description = self.cleaned_data['description']
            plan.edition = self.cleaned_data['edition']
            plan.visibility = self.cleaned_data['visibility']
            plan.max_domains = self.cleaned_data['max_domains']
            plan.is_customer_software_plan = self.cleaned_data['is_customer_software_plan']
            plan.is_annual_plan = self.cleaned_data['is_annual_plan']
            plan.save()
            messages.success(request, "The %s Software Plan was successfully updated." % self.plan.name)


class SoftwarePlanVersionForm(forms.Form):
    """
    A form for updating the software plan
    """
    update_version = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    select2_feature_id = forms.CharField(
        required=False,
        label="Search for or Create Feature",
        widget=forms.Select(choices=[]),
    )
    new_feature_type = forms.ChoiceField(
        required=False,
        choices=FeatureType.CHOICES,
    )
    feature_rates = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    product_rate_id = forms.CharField(
        required=False,
        label="Search for or Create Product",
        widget=forms.Select(choices=[]),
    )
    product_rates = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    privileges = forms.MultipleChoiceField(
        required=False,
        label="Privileges",
        validators=[MinLengthValidator(1)]
    )
    role_slug = forms.ChoiceField(
        required=False,
        label="Role",
        widget=forms.Select(choices=[]),
    )
    role_type = forms.ChoiceField(
        required=True,
        choices=(
            ('existing', "Use Existing Role"),
            ('new', "Create New Role"),
        )
    )
    create_new_role = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput,
    )
    new_role_slug = forms.CharField(
        required=False,
        max_length=256,
        label="New Role Slug",
        help_text="A slug is a short label containing only letters, numbers, underscores or hyphens.",
    )
    new_role_name = forms.CharField(
        required=False,
        max_length=256,
        label="New Role Name",
    )
    new_role_description = forms.CharField(
        required=False,
        label="New Role Description",
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    )
    upgrade_subscriptions = forms.BooleanField(
        label="Automatically upgrade all subscriptions on the "
              "previous version of this plan to this version immediately.",
        required=False,
    )

    new_product_rate = None

    def __init__(self, plan, plan_version, admin_web_user, *args, **kwargs):
        self.plan = plan
        self.plan_version = plan_version
        self.admin_web_user = admin_web_user
        self.is_update = False

        super(SoftwarePlanVersionForm, self).__init__(*args, **kwargs)

        if not self.plan.is_customer_software_plan:
            del self.fields['upgrade_subscriptions']

        self.fields['privileges'].choices = list(self.available_privileges)
        self.fields['role_slug'].choices = [
            (r['slug'], "%s (%s)" % (r['name'], r['slug']))
            for r in self.existing_roles
        ]

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'
        self.helper.form_method = 'POST'

        permissions_fieldset = crispy.Fieldset(
            "Permissions",
            hqcrispy.B3MultiField(
                "Role Type",
                crispy.Div(
                    data_bind="template: {"
                              " name: 'select-role-type-template', "
                              " data: role"
                              "}, "
                ),
            ),
            crispy.Div(
                hqcrispy.B3MultiField(
                    'Role',
                    InlineField(
                        'role_slug',
                        data_bind="value: role.existing.roleSlug",
                        css_class="input-xxlarge",
                        style="width: 100%;",
                    ),
                    crispy.Div(
                        data_bind="template: {"
                                  " name: 'selected-role-privileges-template', "
                                  " data: {"
                                  "     privileges: role.existing.selectedPrivileges,"
                                  "     hasNoPrivileges: role.existing.hasNoPrivileges"
                                  " }"
                                  "}, "
                    ),
                    data_bind="visible: role.isRoleTypeExisting",
                ),
            ),
            crispy.Div(
                hqcrispy.B3MultiField(
                    "Privileges",
                    InlineField('privileges', data_bind="selectedOptions: role.new.privileges"),
                    crispy.Div(
                        data_bind="template: {"
                                  " name: 'privileges-match-role-template', "
                                  " data: {"
                                  "     role: role.new.matchingRole"
                                  " },"
                                  " if: role.new.hasMatchingRole"
                                  "}, "
                    ),
                ),
                crispy.Field('create_new_role', data_bind="value: role.new.allowCreate"),
                crispy.Div(
                    'new_role_slug',
                    'new_role_name',
                    'new_role_description',
                    data_bind="visible: role.new.allowCreate",
                    css_class="well",
                ),
                data_bind="visible: role.isRoleTypeNew",
            ),
        )

        features_fieldset = crispy.Fieldset(
            "Features",
            InlineField('feature_rates', data_bind="value: featureRates.ratesString"),
            hqcrispy.B3MultiField(
                "Add Feature",
                InlineField('select2_feature_id', css_class="input-xxlarge",
                            data_bind="value: featureRates.select2.value"),
                StrictButton(
                    "Select Feature",
                    css_class="btn-primary",
                    data_bind="event: {click: featureRates.apply}, "
                              "visible: featureRates.select2.isExisting",
                    style="margin-left: 5px;"
                ),
            ),
            crispy.Div(
                css_class="alert alert-danger",
                data_bind="text: featureRates.error, visible: featureRates.showError"
            ),
            hqcrispy.B3MultiField(
                "Feature Type",
                InlineField(
                    'new_feature_type',
                    data_bind="value: featureRates.rateType",
                ),
                crispy.Div(
                    StrictButton(
                        "Create Feature",
                        css_class="btn-primary",
                        data_bind="event: {click: featureRates.createNew}",

                    ),
                    style="margin: 10px 0;"
                ),
                data_bind="visible: featureRates.select2.isNew",
            ),
            crispy.Div(
                data_bind="template: {"
                          "name: 'feature-rate-form-template', foreach: featureRates.rates"
                          "}",
            ),
        )

        products_fieldset = crispy.Fieldset(
            "Products",
            InlineField('product_rates', data_bind="value: productRates.ratesString"),
            hqcrispy.B3MultiField(
                "Add Product",
                InlineField('product_rate_id', css_class="input-xxlarge",
                            data_bind="value: productRates.select2.value"),
                StrictButton(
                    "Select Product",
                    css_class="btn-primary",
                    data_bind="event: {click: productRates.apply}, "
                              "visible: productRates.select2.isExisting",
                    style="margin-left: 5px;"
                ),
            ),
            crispy.Div(
                css_class="alert alert-danger",
                data_bind="text: productRates.error, visible: productRates.showError",
            ),
            hqcrispy.B3MultiField(
                "Product Type",
                crispy.Div(
                    StrictButton(
                        "Create Product",
                        css_class="btn-primary",
                        data_bind="event: {click: productRates.createNew}",
                    ),
                    style="margin: 10px 0;"
                ),
                data_bind="visible: productRates.select2.isNew",
            ),
            crispy.Div(
                data_bind="template: {"
                          "name: 'product-rate-form-template', foreach: productRates.rates"
                          "}",
            ),
        )

        layout_fields = [
            'update_version',
            permissions_fieldset,
            features_fieldset,
            products_fieldset
        ]
        if self.plan.is_customer_software_plan:
            layout_fields.append(crispy.Fieldset(
                "Manage Existing Subscriptions",
                'upgrade_subscriptions'
            ))
        layout_fields.append(
            hqcrispy.FormActions(
                StrictButton(
                    'Update Plan Version',
                    css_class='btn-primary disable-on-submit',
                    type="submit",
                ),
            )
        )
        self.helper.layout = crispy.Layout(*layout_fields)

    @property
    def available_privileges(self):
        for priv in privileges.MAX_PRIVILEGES:
            role = Role.objects.get(slug=priv)
            yield (role.slug, role.name)

    @property
    def existing_roles(self):
        roles = set([r['role'] for r in SoftwarePlanVersion.objects.values('role').distinct()])
        grant_roles = set([r['from_role'] for r in Grant.objects.filter(
            to_role__slug__in=privileges.MAX_PRIVILEGES).values('from_role').distinct()])
        roles = roles.union(grant_roles)
        roles = [Role.objects.get(pk=r) for r in roles]
        for role in roles:
            yield {
                'slug': role.slug,
                'name': role.name,
                'description': role.description,
                'privileges': [
                    (grant.to_role.slug, grant.to_role.name)
                    for grant in role.memberships_granted.all()
                ],
            }

    @property
    def feature_rates_dict(self):
        return {
            'currentValue': self['feature_rates'].value(),
            'handlerSlug': FeatureRateAsyncHandler.slug,
            'select2Options': {
                'fieldName': 'select2_feature_id',
            }
        }

    @property
    def product_rates_dict(self):
        return {
            'currentValue': self['product_rates'].value(),
            'handlerSlug': SoftwareProductRateAsyncHandler.slug,
            'select2Options': {
                'fieldName': 'product_rate_id',
            }
        }

    @property
    def role_dict(self):
        return {
            'currentValue': self['privileges'].value(),
            'multiSelectField': {
                'slug': 'privileges',
                'titleSelect': _("Privileges Available"),
                'titleSelected': _("Privileges Selected"),
                'titleSearch': _("Search Privileges..."),
            },
            'existingRoles': list(self.existing_roles),
            'roleType': self['role_type'].value() or 'existing',
            'newPrivileges': self['privileges'].value(),
            'currentRoleSlug': self.plan_version.role.slug if self.plan_version is not None else None,
        }

    @property
    @memoized
    def current_features_to_rates(self):
        if self.plan_version is not None:
            return dict([(r.feature.id, r) for r in self.plan_version.feature_rates.all()])
        else:
            return {}

    @staticmethod
    def _get_errors_from_subform(form_name, subform):
        for field, field_errors in subform._errors.items():
            for field_error in field_errors:
                error_message = "%(form_name)s > %(field_name)s: %(error)s" % {
                    'form_name': form_name,
                    'error': field_error,
                    'field_name': subform[field].label,
                }
                yield error_message

    def _retrieve_feature_rate(self, rate_form):
        feature = Feature.objects.get(id=rate_form['feature_id'].value())
        new_rate = rate_form.get_instance(feature)
        if rate_form.is_new():
            # a brand new rate
            self.is_update = True
            return new_rate
        if feature.id not in self.current_features_to_rates:
            # the plan does not have this rate yet, compare any changes to the feature's current latest rate
            # also mark the form as updated
            current_rate = feature.get_rate(default_instance=False)
            if current_rate is None:
                return new_rate
            self.is_update = True
        else:
            current_rate = self.current_features_to_rates[feature.id]
        # note: custom implementation of FeatureRate.__eq__ here...
        if not (current_rate == new_rate):
            self.is_update = True
            return new_rate
        return current_rate

    def _retrieve_product_rate(self, rate_form):
        new_rate = rate_form.get_instance()
        if rate_form.is_new():
            # a brand new rate
            self.is_update = True
            return new_rate
        try:
            current_rate = SoftwareProductRate.objects.get(id=rate_form['rate_id'].value())
            # note: custom implementation of SoftwareProductRate.__eq__ here...
            if not (current_rate == new_rate):
                self.is_update = True
                return new_rate
            else:
                return current_rate
        except SoftwareProductRate.DoesNotExist:
            self.is_update = True
            return new_rate

    def clean_feature_rates(self):
        original_data = self.cleaned_data['feature_rates']
        rates = json.loads(original_data)
        rate_instances = []
        errors = ErrorList()
        for rate_data in rates:
            rate_form = FeatureRateForm(rate_data)
            if not rate_form.is_valid():
                errors.extend(list(self._get_errors_from_subform(rate_data['name'], rate_form)))
            else:
                rate_instances.append(self._retrieve_feature_rate(rate_form))
        if errors:
            self._errors.setdefault('feature_rates', errors)

        required_types = [FeatureType.USER, FeatureType.SMS]
        all_types = list(dict(FeatureType.CHOICES))
        feature_types = [r.feature.feature_type for r in rate_instances]
        if any([feature_types.count(t) == 0 for t in required_types]):
            raise ValidationError(_(
                "You must specify a rate for SMS and USER feature type"
            ))
        if any([feature_types.count(t) > 1 for t in all_types]):
            raise ValidationError(_(
                "You can only specify one rate per feature type "
                "(SMS, USER, etc.)"
            ))

        self.new_feature_rates = rate_instances

        def rate_ids(rate_list):
            return set([rate.id for rate in rate_list])
        if (
            not self.is_update
            and (
                self.plan_version is None
                or rate_ids(rate_instances).symmetric_difference(
                    rate_ids(self.plan_version.feature_rates.all())
                )
            )
        ):
            self.is_update = True
        return original_data

    def clean_product_rates(self):
        original_data = self.cleaned_data['product_rates']
        rates = json.loads(original_data)
        errors = ErrorList()
        if len(rates) != 1:
            raise ValidationError(_("You must specify exactly one product rate."))
        rate_data = rates[0]
        rate_form = ProductRateForm(rate_data)

        if not rate_form.is_valid():
            errors.extend(list(self._get_errors_from_subform(rate_data['name'], rate_form)))
            self._errors.setdefault('product_rates', errors)
            self.is_update = True
        else:
            self.new_product_rate = self._retrieve_product_rate(rate_form)
            self.is_update = (
                self.is_update
                or self.plan_version is None
                or self.new_product_rate.id != self.plan_version.product_rate.id
            )
        return original_data

    def clean_create_new_role(self):
        val = self.cleaned_data['create_new_role']
        if val:
            self.is_update = True
        return val

    def clean_role_slug(self):
        role_slug = self.cleaned_data['role_slug']
        if self.plan_version is None or role_slug != self.plan_version.role.slug:
            self.is_update = True
        return role_slug

    def clean_new_role_slug(self):
        val = self.cleaned_data['new_role_slug']
        if self.cleaned_data['create_new_role'] and not val:
            raise ValidationError(_("A slug is required for this new role."))
        if val:
            validate_slug(val)
        if Role.objects.filter(slug=val).count() != 0:
            raise ValidationError(_("Enter a unique role slug."))
        return val

    def clean_new_role_name(self):
        val = self.cleaned_data['new_role_name']
        if self.cleaned_data['create_new_role'] and not val:
            raise ValidationError(_("A name is required for this new role."))
        return val

    @transaction.atomic
    def save(self, request):
        if DefaultProductPlan.objects.filter(plan=self.plan).exists():
            messages.warning(request, "You cannot modify a non-custom software plan.")
            return
        if not self.is_update:
            messages.info(request, "No changes to rates and roles were present, so the current version was kept.")
            return
        if self.cleaned_data['create_new_role']:
            role = Role.objects.create(
                slug=self.cleaned_data['new_role_slug'],
                name=self.cleaned_data['new_role_name'],
                description=self.cleaned_data['new_role_description'],
            )
            for privilege in self.cleaned_data['privileges']:
                privilege = Role.objects.get(slug=privilege)
                Grant.objects.create(
                    from_role=role,
                    to_role=privilege,
                )
        else:
            role = Role.objects.get(slug=self.cleaned_data['role_slug'])
        new_version = SoftwarePlanVersion(
            plan=self.plan,
            role=role
        )

        self.new_product_rate.save()
        new_version.product_rate = self.new_product_rate
        new_version.save()

        for feature_rate in self.new_feature_rates:
            feature_rate.save()
            new_version.feature_rates.add(feature_rate)
        new_version.save()

        messages.success(
            request,
            'The version for %s Software Plan was successfully updated.' % new_version.plan.name
        )

        if self.plan.is_customer_software_plan and self.cleaned_data['upgrade_subscriptions']:
            upgrade_subscriptions_to_latest_plan_version(
                self.plan_version,
                self.admin_web_user,
                upgrade_note="Immediately upgraded when creating a new version."
            )
            messages.success(
                request,
                "All subscriptions on the previous version of this plan were "
                "also upgraded to this new version."
            )


class FeatureRateForm(forms.ModelForm):
    """
    A form for creating a new FeatureRate.
    """
    # feature id will point to a select2 field, hence the CharField here.
    feature_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    rate_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta(object):
        model = FeatureRate
        fields = ['monthly_fee', 'monthly_limit', 'per_excess_fee']

    def __init__(self, data=None, *args, **kwargs):
        super(FeatureRateForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML("""
                        <h4><span data-bind="text: name"></span>
                        <span class="label label-default"
                            style="display: inline-block; margin: 0 10px;"
                            data-bind="text: feature_type"></span></h4>
                        <hr />
            """),
            crispy.Field('feature_id', data_bind="value: feature_id"),
            crispy.Field('rate_id', data_bind="value: rate_id"),
            crispy.Field('monthly_fee', data_bind="value: monthly_fee"),
            crispy.Field('monthly_limit', data_bind="value: monthly_limit"),
            crispy.Div(
                crispy.Field('per_excess_fee',
                             data_bind="value: per_excess_fee"),
                data_bind="visible: isPerExcessVisible",
            ),
        )

    def is_new(self):
        return not self['rate_id'].value()

    def get_instance(self, feature):
        instance = self.save(commit=False)
        instance.feature = feature
        return instance


class ProductRateForm(forms.ModelForm):
    """
    A form for creating a new ProductRate.
    """

    name = forms.CharField(
        required=True,
        widget=forms.HiddenInput,
    )

    rate_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta(object):
        model = SoftwareProductRate
        fields = ['monthly_fee', 'name']

    def __init__(self, data=None, *args, **kwargs):
        super(ProductRateForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML("""
                        <h4><span data-bind="text: name"></span></h4>
                        <hr />
            """),
            crispy.Field('monthly_fee', data_bind="value: monthly_fee"),
        )

    def is_new(self):
        return not self['rate_id'].value()

    def get_instance(self):
        return self.save(commit=False)


class EnterprisePlanContactForm(forms.Form):
    name = forms.CharField(
        label=gettext_noop("Name")
    )
    company_name = forms.CharField(
        required=False,
        label=gettext_noop("Company / Organization")
    )
    message = forms.CharField(
        required=False,
        label=gettext_noop("Message"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"})
    )

    def __init__(self, domain, web_user, data=None, *args, **kwargs):
        self.domain = domain
        self.web_user = web_user
        super(EnterprisePlanContactForm, self).__init__(data, *args, **kwargs)
        from corehq.apps.domain.views.accounting import SelectPlanView
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = "form-horizontal"
        self.helper.layout = crispy.Layout(
            'name',
            'company_name',
            'message',
            hqcrispy.FormActions(
                hqcrispy.LinkButton(
                    _("Select different plan"),
                    reverse(SelectPlanView.urlname, args=[self.domain]),
                    css_class="btn btn-default"
                ),
                StrictButton(
                    _("Request Quote"),
                    type="submit",
                    css_class="btn-primary",
                ),
            )
        )

    def send_message(self):
        subject = "[Enterprise Plan Request] %s" % self.domain
        context = {
            'name': self.cleaned_data['name'],
            'company': self.cleaned_data['company_name'],
            'message': self.cleaned_data['message'],
            'domain': self.domain,
            'email': self.web_user.email
        }
        html_content = render_to_string('accounting/email/sales_request.html', context)
        text_content = """
        Email: %(email)s
        Name: %(name)s
        Company: %(company)s
        Domain: %(domain)s
        Message:
        %(message)s
        """ % context
        send_html_email_async.delay(subject, settings.BILLING_EMAIL,
                                    html_content, text_content,
                                    email_from=settings.DEFAULT_FROM_EMAIL)


class AnnualPlanContactForm(forms.Form):
    name = forms.CharField(
        label=gettext_noop("Name")
    )
    company_name = forms.CharField(
        required=False,
        label=gettext_noop("Company / Organization")
    )
    message = forms.CharField(
        required=False,
        label=gettext_noop("Message"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"})
    )

    def __init__(self, domain, web_user, on_annual_plan, data=None, *args, **kwargs):
        self.domain = domain
        self.web_user = web_user
        super(AnnualPlanContactForm, self).__init__(data, *args, **kwargs)
        from corehq.apps.domain.views.accounting import SelectPlanView, DomainSubscriptionView
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = "form-horizontal"
        if on_annual_plan:
            back_button_text = "Back to my Subscription"
            urlname = DomainSubscriptionView.urlname
        else:
            back_button_text = "Select different plan"
            urlname = SelectPlanView.urlname
        self.helper.layout = crispy.Layout(
            'name',
            'company_name',
            'message',
            hqcrispy.FormActions(
                hqcrispy.LinkButton(
                    _(back_button_text),
                    reverse(urlname, args=[self.domain]),
                    css_class="btn btn-default"
                ),
                StrictButton(
                    _("Submit"),
                    type="submit",
                    css_class="btn-primary",
                ),
            )
        )

    def send_message(self):
        subject = "[Annual Plan Request] %s" % self.domain
        context = {
            'name': self.cleaned_data['name'],
            'company': self.cleaned_data['company_name'],
            'message': self.cleaned_data['message'],
            'domain': self.domain,
            'email': self.web_user.email
        }
        html_content = render_to_string('accounting/email/sales_request.html', context)
        text_content = """
        Email: %(email)s
        Name: %(name)s
        Company: %(company)s
        Domain: %(domain)s
        Message:
        %(message)s
        """ % context
        send_html_email_async.delay(subject, settings.BILLING_EMAIL,
                                    html_content, text_content,
                                    email_from=settings.DEFAULT_FROM_EMAIL)


class TriggerInvoiceForm(forms.Form):
    month = forms.ChoiceField(label="Statement Period Month")
    year = forms.ChoiceField(label="Statement Period Year")
    domain = forms.CharField(label="Project Space", widget=forms.Select(choices=[]))
    num_users = forms.IntegerField(
        label="Number of Users",
        required=False,
        help_text="This is part of accounting tests and overwrites the "
                  "DomainUserHistory recorded for this month. Please leave "
                  "this blank to use what is already in the system."
    )

    def __init__(self, *args, **kwargs):
        self.show_testing_options = kwargs.pop('show_testing_options')
        super(TriggerInvoiceForm, self).__init__(*args, **kwargs)
        today = datetime.date.today()
        one_month_ago = today - relativedelta(months=1)

        self.fields['month'].initial = one_month_ago.month
        self.fields['month'].choices = list(MONTHS.items())
        self.fields['year'].initial = one_month_ago.year
        self.fields['year'].choices = [
            (y, y) for y in range(one_month_ago.year, 2012, -1)
        ]

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'

        details = [
            'Trigger Invoice Details',
            crispy.Field('month', css_class="input-large"),
            crispy.Field('year', css_class="input-large"),
            crispy.Field(
                'domain',
                css_class="input-xxlarge accounting-async-select2",
                placeholder="Search for Project"
            )
        ]
        if self.show_testing_options:
            details.append(crispy.Field('num_users', css_class='input_large'))
        else:
            del self.fields['num_users']

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(*details),
            hqcrispy.FormActions(
                StrictButton(
                    "Trigger Invoice",
                    css_class="btn-primary disable-on-submit",
                    type="submit",
                ),
            )
        )

    @transaction.atomic
    def trigger_invoice(self):
        year = int(self.cleaned_data['year'])
        month = int(self.cleaned_data['month'])
        invoice_start, invoice_end = get_first_last_days(year, month)
        domain_obj = Domain.get_by_name(self.cleaned_data['domain'])

        self.clean_previous_invoices(invoice_start, invoice_end, domain_obj.name)

        if self.show_testing_options and self.cleaned_data['num_users']:
            num_users = int(self.cleaned_data['num_users'])
            existing_histories = DomainUserHistory.objects.filter(
                domain=domain_obj.name,
                record_date__gte=invoice_start,
                record_date__lte=invoice_end,
            )
            if existing_histories.exists():
                existing_histories.all().delete()
            DomainUserHistory.objects.create(
                domain=domain_obj.name,
                record_date=invoice_end,
                num_users=num_users
            )

        invoice_factory = DomainInvoiceFactory(
            invoice_start, invoice_end, domain_obj, recipients=[settings.ACCOUNTS_EMAIL]
        )
        invoice_factory.create_invoices()

    @staticmethod
    def clean_previous_invoices(invoice_start, invoice_end, domain_name):
        prev_invoices = Invoice.objects.filter(
            date_start__lte=invoice_end, date_end__gte=invoice_start,
            subscription__subscriber__domain=domain_name
        )
        if prev_invoices.count() > 0:
            from corehq.apps.accounting.views import InvoiceSummaryView
            raise InvoiceError(
                "Invoices exist that were already generated with this same "
                "criteria. You must manually suppress these invoices: "
                "{invoice_list}".format(
                    invoice_list=', '.join(
                        ['<a href="{edit_url}">{name}</a>'.format(
                            edit_url=reverse(InvoiceSummaryView.urlname, args=(x.id,)),
                            name=x.invoice_number
                        ) for x in prev_invoices.all()]
                    ),
                )
            )

    def clean(self):
        today = datetime.date.today()
        year = int(self.cleaned_data['year'])
        month = int(self.cleaned_data['month'])

        if (year, month) >= (today.year, today.month):
            raise ValidationError('Statement period must be in the past')


class TriggerCustomerInvoiceForm(forms.Form):
    month = forms.ChoiceField(label="Statement Period Month")
    year = forms.ChoiceField(label="Statement Period Year")
    customer_account = forms.CharField(label="Billing Account", widget=forms.Select(choices=[]))

    def __init__(self, *args, **kwargs):
        super(TriggerCustomerInvoiceForm, self).__init__(*args, **kwargs)
        today = datetime.date.today()
        one_month_ago = today - relativedelta(months=1)
        self.fields['month'].initial = one_month_ago.month
        self.fields['month'].choices = list(MONTHS.items())
        self.fields['year'].initial = one_month_ago.year
        self.fields['year'].choices = [
            (y, y) for y in range(one_month_ago.year, 2012, -1)
        ]
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Trigger Customer Invoice Details',
                crispy.Field('month', css_class="input-large"),
                crispy.Field('year', css_class="input-large"),
                crispy.Field('customer_account', css_class="input-xxlarge accounting-async-select2",
                             placeholder="Search for Customer Billing Account")
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Trigger Customer Invoice",
                    css_class="btn-primary disable-on-submit",
                    type="submit",
                ),
            )
        )

    @transaction.atomic
    def trigger_customer_invoice(self):
        year = int(self.cleaned_data['year'])
        month = int(self.cleaned_data['month'])
        try:
            account = BillingAccount.objects.get(name=self.cleaned_data['customer_account'])
            invoice_start, invoice_end = self.get_invoice_dates(account, year, month)
            self.clean_previous_invoices(invoice_start, invoice_end, account)
            invoice_factory = CustomerAccountInvoiceFactory(
                date_start=invoice_start,
                date_end=invoice_end,
                account=account,
                recipients=[settings.ACCOUNTS_EMAIL]
            )
            invoice_factory.create_invoice()
        except BillingAccount.DoesNotExist:
            raise InvoiceError(
                "There is no Billing Account associated with %s" % self.cleaned_data['customer_account']
            )

    @staticmethod
    def clean_previous_invoices(invoice_start, invoice_end, account):
        prev_invoices = CustomerInvoice.objects.filter(
            date_start__lte=invoice_end,
            date_end__gte=invoice_start,
            account=account
        )
        if prev_invoices:
            from corehq.apps.accounting.views import CustomerInvoiceSummaryView
            raise InvoiceError(
                "Invoices exist that were already generated with this same "
                "criteria. You must manually suppress these invoices: "
                "{invoice_list}".format(
                    invoice_list=', '.join(
                        ['<a href="{edit_url}">{name}</a>'.format(
                            edit_url=reverse(CustomerInvoiceSummaryView.urlname, args=(x.id,)),
                            name=x.invoice_number
                        ) for x in prev_invoices]
                    ),
                )
            )

    def clean(self):
        today = datetime.date.today()
        year = int(self.cleaned_data['year'])
        month = int(self.cleaned_data['month'])
        if (year, month) >= (today.year, today.month):
            raise ValidationError('Statement period must be in the past')

    def get_invoice_dates(self, account, year, month):
        if account.invoicing_plan == InvoicingPlan.YEARLY:
            if month == 12:
                # Set invoice start date to January 1st
                return datetime.date(year, 1, 1), datetime.date(year, 12, 31)
            else:
                raise InvoiceError(
                    "%s is set to be invoiced yearly, and you may not invoice in this month. "
                    "You must select December in the year for which you are triggering an annual invoice."
                    % self.cleaned_data['customer_account']
                )
        if account.invoicing_plan == InvoicingPlan.QUARTERLY:
            if month == 3:
                return datetime.date(year, 1, 1), datetime.date(year, 3, 31)    # Quarter 1
            if month == 6:
                return datetime.date(year, 4, 1), datetime.date(year, 6, 30)    # Quarter 2
            if month == 9:
                return datetime.date(year, 7, 1), datetime.date(year, 9, 30)    # Quarter 3
            if month == 12:
                return datetime.date(year, 10, 1), datetime.date(year, 12, 31)  # Quarter 4
            else:
                raise InvoiceError(
                    "%s is set to be invoiced quarterly, and you may not invoice in this month. "
                    "You must select the last month of a quarter to trigger a quarterly invoice."
                    % self.cleaned_data['customer_account']
                )
        else:
            return get_first_last_days(year, month)


class TriggerBookkeeperEmailForm(forms.Form):
    month = forms.ChoiceField(label="Invoice Month")
    year = forms.ChoiceField(label="Invoice Year")
    emails = forms.CharField(label="Email To", widget=forms.SelectMultiple(choices=[]),)

    def __init__(self, *args, **kwargs):
        super(TriggerBookkeeperEmailForm, self).__init__(*args, **kwargs)
        today = datetime.date.today()

        self.fields['month'].initial = today.month
        self.fields['month'].choices = list(MONTHS.items())
        self.fields['year'].initial = today.year
        self.fields['year'].choices = [
            (y, y) for y in range(today.year, 2012, -1)
        ]

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Trigger Bookkeeper Email Details',
                crispy.Field('emails', css_class='input-xxlarge accounting-email-select2',
                             data_initial=json.dumps(self.initial.get('emails'))),
                crispy.Field('month', css_class="input-large"),
                crispy.Field('year', css_class="input-large"),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Trigger Bookkeeper Email",
                    css_class="btn-primary disable-on-submit",
                    type="submit",
                ),
            )
        )

    def clean_emails(self):
        return self.data.getlist('emails')

    def trigger_email(self):
        from corehq.apps.accounting.tasks import send_bookkeeper_email
        send_bookkeeper_email(
            month=int(self.cleaned_data['month']),
            year=int(self.cleaned_data['year']),
            emails=self.cleaned_data['emails']
        )


class TestReminderEmailFrom(forms.Form):
    days = forms.ChoiceField(
        label="Days Until Subscription Ends",
        choices=(
            (1, 1),
            (10, 10),
            (30, 30),
        )
    )

    def __init__(self, *args, **kwargs):
        super(TestReminderEmailFrom, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "Test Subscription Reminder Emails",
                'days',
            ),
            crispy.Div(
                crispy.HTML(
                    "Note that this will ONLY send emails to a billing admin "
                    "for a domain IF the billing admin is an Accounting "
                    "Previewer."
                ),
                css_class="alert alert-info"
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Send Reminder Emails",
                    type="submit",
                    css_class='btn-primary disable-on-submit'
                )
            )
        )

    def send_emails(self):
        send_subscription_reminder_emails(int(self.cleaned_data['days']))


class AdjustBalanceForm(forms.Form):
    adjustment_type = forms.ChoiceField(
        widget=forms.RadioSelect,
    )

    custom_amount = forms.DecimalField(
        required=False,
    )

    method = forms.ChoiceField(
        choices=(
            (CreditAdjustmentReason.MANUAL, "Register back office payment"),
            (CreditAdjustmentReason.TRANSFER, "Take from available credit lines"),
            (
                CreditAdjustmentReason.FRIENDLY_WRITE_OFF,
                "Forgive amount with a friendly write-off"
            ),
        )
    )

    note = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    )

    invoice_id = forms.CharField(
        widget=forms.HiddenInput(),
    )

    adjust = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, invoice, *args, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        self.fields['adjustment_type'].choices = (
            ('current', 'Pay off Current Balance: %s' %
                        get_money_str(self.invoice.balance)),
            ('credit', 'Pay off Custom Amount'),
        )
        self.fields['invoice_id'].initial = invoice.id
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-4 col-md-3'
        self.helper.field_class = 'col-sm-8 col-md-9'
        if invoice.is_customer_invoice:
            self.helper.form_action = reverse('customer_invoice_summary', args=[self.invoice.id])
        else:
            self.helper.form_action = reverse('invoice_summary', args=[self.invoice.id])
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.Field(
                    'adjustment_type',
                    data_bind="checked: adjustmentType",
                ),
                crispy.HTML('''
                    <div id="div_id_custom_amount" class="form-group"
                     data-bind="visible: showCustomAmount">
                        <label for="id_custom_amount" class="control-label col-sm-4 col-md-3">
                            Custom amount
                        </label>
                        <div class="col-sm-8 col-md-9">
                            <input class="textinput textInput form-control"
                             id="id_custom_amount" name="custom_amount"
                             type="number" step="any">
                        </div>
                    </div>
                '''),
                crispy.Field('method'),
                crispy.Field('note'),
                crispy.Field('invoice_id'),
                'adjust',
                css_class='modal-body ko-adjust-balance-form',
            ),
            crispy.Div(
                crispy.Submit(
                    'adjust_balance',
                    'Apply',
                    css_class='disable-on-submit',
                    data_loading_text='Submitting...',
                ),
                crispy.Button(
                    'close',
                    'Close',
                    css_class='disable-on-submit btn-default',
                    data_dismiss='modal',
                ),
                css_class='modal-footer',
            ),
        )

    @property
    @memoized
    def amount(self):
        adjustment_type = self.cleaned_data['adjustment_type']
        if adjustment_type == 'current':
            return self.invoice.balance
        elif adjustment_type == 'credit':
            return Decimal(self.cleaned_data['custom_amount'])
        else:
            raise ValidationError(_("Received invalid adjustment type: %s")
                                  % adjustment_type)

    @transaction.atomic
    def adjust_balance(self, web_user=None):
        method = self.cleaned_data['method']
        kwargs = {
            'account': (self.invoice.account if self.invoice.is_customer_invoice
                        else self.invoice.subscription.account),
            'note': self.cleaned_data['note'],
            'reason': method,
            'subscription': None if self.invoice.is_customer_invoice else self.invoice.subscription,
            'web_user': web_user,
        }
        if method in [
            CreditAdjustmentReason.MANUAL,
            CreditAdjustmentReason.FRIENDLY_WRITE_OFF,
        ]:
            if self.invoice.is_customer_invoice:
                CreditLine.add_credit(
                    -self.amount,
                    customer_invoice=self.invoice,
                    **kwargs
                )
            else:
                CreditLine.add_credit(
                    -self.amount,
                    invoice=self.invoice,
                    **kwargs
                )
            CreditLine.add_credit(
                self.amount,
                permit_inactive=True,
                **kwargs
            )
        elif method == CreditAdjustmentReason.TRANSFER:
            if self.invoice.is_customer_invoice:
                subscription_invoice = None
                customer_invoice = self.invoice
                credit_line_balance = sum(
                    credit_line.balance
                    for credit_line in CreditLine.get_credits_for_customer_invoice(self.invoice)
                )
            else:
                subscription_invoice = self.invoice
                customer_invoice = None
                credit_line_balance = sum(
                    credit_line.balance
                    for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
                )
            transfer_balance = (
                min(self.amount, credit_line_balance)
                if credit_line_balance > 0 else min(0, self.amount)
            )
            CreditLine.add_credit(
                -transfer_balance,
                invoice=subscription_invoice,
                customer_invoice=customer_invoice,
                **kwargs
            )

        self.invoice.update_balance()
        self.invoice.save()


class InvoiceInfoForm(forms.Form):

    subscription = forms.CharField()
    project = forms.CharField()
    account = forms.CharField()
    current_balance = forms.CharField()

    def __init__(self, invoice, *args, **kwargs):
        self.invoice = invoice
        subscription = invoice.subscription if not (invoice.is_wire or invoice.is_customer_invoice) else None
        super(InvoiceInfoForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form-horizontal'
        from corehq.apps.accounting.views import (
            EditSubscriptionView,
            ManageBillingAccountView,
        )
        if not invoice.is_wire and not invoice.is_customer_invoice:
            subscription_link = make_anchor_tag(
                reverse(EditSubscriptionView.urlname, args=(subscription.id,)),
                format_html(
                    '{plan_name} ({start_date} - {end_date})',
                    plan_name=subscription.plan_version,
                    start_date=subscription.date_start,
                    end_date=subscription.date_end,
                )
            )
        else:
            subscription_link = 'N/A'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '{} Invoice #{}'.format('Customer' if invoice.is_customer_invoice else
                                        'Wire' if invoice.is_wire else '', invoice.invoice_number),
            )

        )
        if not invoice.is_customer_invoice:
            self.helper.layout[0].extend([
                hqcrispy.B3TextField(
                    'subscription',
                    subscription_link
                ),
                hqcrispy.B3TextField(
                    'project',
                    invoice.get_domain(),
                )
            ])
        self.helper.layout[0].extend([
            hqcrispy.B3TextField(
                'account',
                format_html(
                    '<a href="{}">Super {}</a>',
                    reverse(
                        ManageBillingAccountView.urlname,
                        args=(invoice.account.id,)
                    ),
                    invoice.account.name
                ),
            ),
            hqcrispy.B3TextField(
                'current_balance',
                get_money_str(invoice.balance),
            ),
            hqcrispy.B3MultiField(
                'Balance Adjustments',
                crispy.Button(
                    'submit',
                    'Adjust Balance',
                    data_toggle='modal',
                    data_target='#adjustBalanceModal-%d' % invoice.id,
                    css_class=('btn-default disabled'
                               if invoice.is_wire
                               else 'btn-default') + ' disable-on-submit',
                ),
            )
        ])


class ResendEmailForm(forms.Form):

    additional_recipients = forms.CharField(
        label="Additional Recipients:",
        required=False,
    )
    resend = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, invoice, *args, **kwargs):
        self.invoice = invoice
        super(ResendEmailForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Div(
                crispy.HTML(
                    'This will send an email to: %s.' %
                    ', '.join(invoice.email_recipients)
                ),
                crispy.Field('additional_recipients'),
                'resend',
                css_class='modal-body',
            ),
            crispy.Div(
                crispy.Submit(
                    'resend_email',
                    'Send Email',
                    css_class='disable-on-submit',
                    data_loading_text='Submitting...',
                ),
                crispy.Button(
                    'close',
                    'Close',
                    css_class='disable-on-submit btn-default',
                    data_dismiss='modal',
                ),
                css_class='modal-footer',
            ),
        )

    def clean_additional_recipients(self):
        return [
            email.strip()
            for email in self.cleaned_data['additional_recipients'].split(',')
        ]

    def resend_email(self):
        contact_emails = set(self.invoice.email_recipients) | set(self.cleaned_data['additional_recipients'])
        if self.invoice.is_wire:
            record = WireBillingRecord.generate_record(self.invoice)
        elif self.invoice.is_customer_invoice:
            record = CustomerBillingRecord.generate_record(self.invoice)
        else:
            record = BillingRecord.generate_record(self.invoice)
        for email in contact_emails:
            record.send_email(contact_email=email)


class SuppressInvoiceForm(forms.Form):
    submit_kwarg = 'suppress'
    suppress = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, invoice, *args, **kwargs):
        self.invoice = invoice
        super(SuppressInvoiceForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Suppress invoice from all reports and user-facing statements',
                crispy.Div(
                    crispy.HTML('Warning: this can only be undone by a developer.'),
                    css_class='alert alert-danger',
                ),
                'suppress',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    'Suppress Invoice',
                    css_class='btn-danger disable-on-submit',
                    name=self.submit_kwarg,
                    type='submit',
                ),
            ),
        )

    def suppress_invoice(self):
        self.invoice.is_hidden_to_ops = True
        self.invoice.save()


class HideInvoiceForm(forms.Form):
    submit_kwarg = 'hide'
    hide = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, invoice, *args, **kwargs):
        self.invoice = invoice
        super(HideInvoiceForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Hide invoice from customer.',
                crispy.Div(
                    crispy.HTML('Warning: this can only be undone by a developer.'),
                    css_class='alert alert-danger',
                ),
                'hide',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    'Hide Invoice',
                    css_class='btn-danger disable-on-submit',
                    name=self.submit_kwarg,
                    type='submit',
                ),
            ),
        )

    def hide_invoice(self):
        self.invoice.is_hidden = True
        self.invoice.save()


class CreateAdminForm(forms.Form):
    username = forms.CharField(
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(CreateAdminForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_show_labels = False
        self.helper.form_style = 'inline'
        self.helper.layout = crispy.Layout(
            InlineField(
                'username',
                css_id="select-admin-username",
            ),
            StrictButton(
                format_html('<i class="fa fa-plus"></i> {}', 'Add Admin'),
                css_class="btn-primary disable-on-submit",
                type="submit",
            )
        )

    @transaction.atomic
    def add_admin_user(self):
        # create UserRole for user
        username = self.cleaned_data['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CreateAccountingAdminError(
                "User '%s' does not exist" % username
            )
        web_user = WebUser.get_by_username(username)
        if not web_user or not web_user.is_superuser:
            raise CreateAccountingAdminError(
                "The user '%s' is not a superuser." % username,
            )
        try:
            user_role = UserRole.objects.get(user=user)
        except UserRole.DoesNotExist:
            user_privs = Role.objects.get_or_create(
                name="Privileges for %s" % user.username,
                slug="%s_privileges" % user.username,
            )[0]
            user_role = UserRole.objects.create(
                user=user,
                role=user_privs,
            )
        ops_role = Role.objects.get(slug=privileges.OPERATIONS_TEAM)
        if not user_role.role.has_privilege(ops_role):
            Grant.objects.create(from_role=user_role.role, to_role=ops_role)
        return user


class TriggerDowngradeForm(forms.Form):
    domain = forms.CharField(label="Project Space", widget=forms.Select(choices=[]))

    def __init__(self, *args, **kwargs):
        super(TriggerDowngradeForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Trigger Downgrade Details',
                crispy.Field(
                    'domain',
                    css_class="input-xxlarge accounting-async-select2",
                    placeholder="Search for Project"
                ),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Trigger Downgrade",
                    css_class="btn-primary disable-on-submit",
                    type="submit",
                ),
            )
        )


class TriggerAutopaymentsForm(forms.Form):
    domain = forms.CharField(label="Project Space", widget=forms.Select(choices=[]))

    def __init__(self, *args, **kwargs):
        super(TriggerAutopaymentsForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form form-horizontal'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Trigger Autopayments Details',
                crispy.Field(
                    'domain',
                    css_class="input-xxlarge accounting-async-select2",
                    placeholder="Search for Project"
                ),
            ),
            hqcrispy.FormActions(
                StrictButton(
                    "Trigger Autopayments for Project",
                    css_class="btn-primary disable-on-submit",
                    type="submit",
                ),
            )
        )
