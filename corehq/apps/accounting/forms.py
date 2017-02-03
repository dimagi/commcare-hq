import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import json

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import MinLengthValidator, validate_slug
from django.db import transaction
from django.forms.utils import ErrorList
from django.template.loader import render_to_string
from django.utils.dates import MONTHS
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.helper import FormHelper
from corehq.apps.style import crispy as hqcrispy
from django_countries.data import COUNTRIES

from dimagi.utils.decorators.memoized import memoized
from django_prbac.models import Role, Grant, UserRole

from corehq import privileges
from corehq.apps.accounting.async_handlers import (
    FeatureRateAsyncHandler,
    SoftwareProductRateAsyncHandler,
)
from corehq.apps.accounting.exceptions import (
    CreateAccountingAdminError,
    InvoiceError,
)
from corehq.apps.accounting.invoicing import DomainInvoiceFactory
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingContactInfo,
    BillingRecord,
    CreditAdjustment,
    CreditAdjustmentReason,
    CreditLine,
    Currency,
    DefaultProductPlan,
    EntryPoint,
    Feature,
    FeatureRate,
    FeatureType,
    FundingSource,
    Invoice,
    LastPayment,
    PreOrPostPay,
    ProBonoStatus,
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    SoftwarePlanVisibility,
    SoftwareProduct,
    SoftwareProductRate,
    SoftwareProductType,
    Subscription,
    SubscriptionType,
    WireBillingRecord,
)
from corehq.apps.accounting.tasks import send_subscription_reminder_emails
from corehq.apps.accounting.utils import (
    get_money_str,
    has_subscription_already_ended,
    make_anchor_tag,
)
from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser
from corehq.util.dates import get_first_last_days


class BillingAccountBasicForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label=ugettext_lazy("Salesforce Account ID"),
                                            max_length=80,
                                            required=False)
    currency = forms.ChoiceField(label="Currency")

    email_list = forms.CharField(
        label=ugettext_lazy('Client Contact Emails'),
    )
    is_active = forms.BooleanField(
        label=ugettext_lazy("Account is Active"),
        required=False,
        initial=True,
    )
    active_accounts = forms.IntegerField(
        label=ugettext_lazy("Transfer Subscriptions To"),
        help_text=ugettext_lazy(
            "Transfer any existing subscriptions to the "
            "Billing Account specified here."
        ),
        required=False,
    )
    dimagi_contact = forms.EmailField(
        label=ugettext_lazy("Dimagi Contact Email"),
        max_length=BillingAccount._meta.get_field('dimagi_contact').max_length,
        required=False,
    )
    entry_point = forms.ChoiceField(
        label=ugettext_lazy("Entry Point"),
        choices=EntryPoint.CHOICES,
    )
    last_payment_method = forms.ChoiceField(
        label=ugettext_lazy("Last Payment Method"),
        choices=LastPayment.CHOICES
    )
    pre_or_post_pay = forms.ChoiceField(
        label=ugettext_lazy("Prepay or Postpay"),
        choices=PreOrPostPay.CHOICES
    )
    account_basic = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, account, *args, **kwargs):
        self.account = account
        if account is not None:
            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            kwargs['initial'] = {
                'name': account.name,
                'salesforce_account_id': account.salesforce_account_id,
                'currency': account.currency.code,
                'email_list': ','.join(contact_info.email_list),
                'is_active': account.is_active,
                'dimagi_contact': account.dimagi_contact,
                'entry_point': account.entry_point,
                'last_payment_method': account.last_payment_method,
                'pre_or_post_pay': account.pre_or_post_pay,
            }
        else:
            kwargs['initial'] = {
                'currency': Currency.get_default().code,
                'entry_point': EntryPoint.CONTRACTED,
                'last_payment_method': LastPayment.NONE,
                'pre_or_post_pay': PreOrPostPay.POSTPAY,
            }
        super(BillingAccountBasicForm, self).__init__(*args, **kwargs)
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
        self.helper = FormHelper()
        self.helper.form_id = "account-form"
        self.helper.form_class = "form-horizontal"
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        additional_fields = []
        if account is not None:
            additional_fields.append(hqcrispy.B3MultiField(
                "Active Status",
                crispy.Field(
                    'is_active',
                    data_bind="checked: is_active",
                ),
            ))
            if account.subscription_set.count() > 0:
                additional_fields.append(crispy.Div(
                    crispy.Field(
                        'active_accounts',
                        css_class="input-xxlarge",
                        placeholder="Select Active Account",
                    ),
                    data_bind="visible: showActiveAccounts"
                ))
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                'Basic Information',
                'name',
                crispy.Field('email_list', css_class='input-xxlarge'),
                crispy.Div(
                    crispy.Div(
                        css_class='col-sm-3 col-md-2'
                    ),
                    crispy.Div(
                        crispy.HTML(self.initial['email_list']),
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
        return self.cleaned_data['email_list'].split(',')

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
            name=name,
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

    class Meta:
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
                    css_class="input-xlarge",
                    data_countryname=COUNTRIES.get(
                        args[0].get('country') if len(args) > 0
                        else account.billingcontactinfo.country,
                        ''
                    )
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
        label=ugettext_lazy("Billing Account")
    )
    start_date = forms.DateField(
        label=ugettext_lazy("Start Date"), widget=forms.DateInput()
    )
    end_date = forms.DateField(
        label=ugettext_lazy("End Date"), widget=forms.DateInput(), required=False
    )
    delay_invoice_until = forms.DateField(
        label=ugettext_lazy("Delay Invoice Until"), widget=forms.DateInput(), required=False
    )
    plan_product = forms.ChoiceField(
        label=ugettext_lazy("Core Product"), initial=SoftwareProductType.COMMCARE,
        choices=SoftwareProductType.CHOICES,
    )
    plan_edition = forms.ChoiceField(
        label=ugettext_lazy("Edition"), initial=SoftwarePlanEdition.ENTERPRISE,
        choices=SoftwarePlanEdition.CHOICES,
    )
    plan_version = forms.IntegerField(label=ugettext_lazy("Software Plan"))
    domain = forms.CharField(label=ugettext_lazy("Project Space"))
    salesforce_contract_id = forms.CharField(
        label=ugettext_lazy("Salesforce Deployment ID"), max_length=80, required=False
    )
    do_not_invoice = forms.BooleanField(
        label=ugettext_lazy("Do Not Invoice"), required=False
    )
    no_invoice_reason = forms.CharField(
        label=ugettext_lazy("Justify why \"Do Not Invoice\""), max_length=256, required=False
    )
    do_not_email_invoice = forms.BooleanField(label="Do Not Email Invoices", required=False)
    do_not_email_reminder = forms.BooleanField(label="Do Not Email Subscription Reminders", required=False)
    auto_generate_credits = forms.BooleanField(
        label=ugettext_lazy("Auto-generate Plan Credits"), required=False
    )
    skip_invoicing_if_no_feature_charges = forms.BooleanField(
        label=ugettext_lazy("Skip invoicing if no feature charges"), required=False
    )
    active_accounts = forms.IntegerField(
        label=ugettext_lazy("Transfer Subscription To"),
        required=False,
    )
    service_type = forms.ChoiceField(
        label=ugettext_lazy("Type"),
        choices=SubscriptionType.CHOICES,
        initial=SubscriptionType.IMPLEMENTATION,
    )
    pro_bono_status = forms.ChoiceField(
        label=ugettext_lazy("Discounted"),
        choices=ProBonoStatus.CHOICES,
        initial=ProBonoStatus.NO,
    )
    funding_source = forms.ChoiceField(
        label=ugettext_lazy("Funding Source"),
        choices=FundingSource.CHOICES,
        initial=FundingSource.CLIENT,
    )
    skip_auto_downgrade = forms.BooleanField(
        label=ugettext_lazy("Exclude from automated downgrade process"),
        required=False
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
        delay_invoice_until_field = crispy.Field('delay_invoice_until',
                                                 css_class="date-picker")

        if is_existing:
            # circular import
            from corehq.apps.accounting.views import (
                ViewSoftwarePlanVersionView, ManageBillingAccountView
            )
            from corehq.apps.domain.views import DefaultProjectSettingsView
            self.fields['account'].initial = subscription.account.id
            account_field = hqcrispy.B3TextField(
                'account',
                '<a href="%(account_url)s">%(account_name)s</a>' % {
                    'account_url': reverse(ManageBillingAccountView.urlname,
                                           args=[subscription.account.id]),
                    'account_name': subscription.account.name,
                }
            )

            self.fields['plan_version'].initial = subscription.plan_version.id
            plan_version_field = hqcrispy.B3TextField(
                'plan_version',
                '<a href="%(plan_version_url)s">%(plan_name)s</a>' % {
                    'plan_version_url': reverse(
                        ViewSoftwarePlanVersionView.urlname,
                        args=[subscription.plan_version.plan.id, subscription.plan_version_id]
                    ),
                    'plan_name': subscription.plan_version,
                },
            )
            self.fields['plan_edition'].initial = subscription.plan_version.plan.edition
            plan_edition_field = hqcrispy.B3TextField(
                'plan_edition',
                self.fields['plan_edition'].initial
            )

            self.fields['domain'].choices = [
                (subscription.subscriber.domain, subscription.subscriber.domain)
            ]
            self.fields['domain'].initial = subscription.subscriber.domain

            domain_field = hqcrispy.B3TextField(
                'domain',
                '<a href="%(project_url)s">%(project_name)s</a>' % {
                    'project_url': reverse(DefaultProjectSettingsView.urlname,
                                           args=[subscription.subscriber.domain]),
                    'project_name': subscription.subscriber.domain,
                },
            )

            self.fields['start_date'].initial = subscription.date_start.isoformat()
            self.fields['end_date'].initial = (
                subscription.date_end.isoformat()
                if subscription.date_end is not None else subscription.date_end
            )
            self.fields['delay_invoice_until'].initial = subscription.date_delay_invoicing
            self.fields['domain'].initial = subscription.subscriber.domain
            self.fields['salesforce_contract_id'].initial = subscription.salesforce_contract_id
            self.fields['do_not_invoice'].initial = subscription.do_not_invoice
            self.fields['no_invoice_reason'].initial = subscription.no_invoice_reason
            self.fields['do_not_email_invoice'].initial = subscription.do_not_email_invoice
            self.fields['do_not_email_reminder'].initial = subscription.do_not_email_reminder
            self.fields['auto_generate_credits'].initial = subscription.auto_generate_credits
            self.fields['skip_invoicing_if_no_feature_charges'].initial = subscription.skip_invoicing_if_no_feature_charges
            self.fields['service_type'].initial = subscription.service_type
            self.fields['pro_bono_status'].initial = subscription.pro_bono_status
            self.fields['funding_source'].initial = subscription.funding_source
            self.fields['skip_auto_downgrade'].initial = subscription.skip_auto_downgrade

            if (
                subscription.date_start is not None
                and subscription.date_start <= today
            ):
                self.fields['start_date'].help_text = '(already started)'
            if has_subscription_already_ended(subscription):
                self.fields['end_date'].help_text = '(already ended)'
            if (
                subscription.date_delay_invoicing is not None
                and subscription.date_delay_invoicing <= today
            ):
                delay_invoice_until_field = hqcrispy.B3TextField(
                    'delay_invoice_until',
                    "%(delay_date)s (date has already passed)" % {
                        'delay_date': self.fields['delay_invoice_until'].initial,
                    }
                )

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
            plan_version_field = crispy.Field(
                'plan_version', css_class="input-xxlarge",
                placeholder="Search for Software Plan"
            )

        plan_product_field = self.plan_product_field()
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_text_inline = True
        transfer_fields = []
        if is_existing:
            transfer_fields.extend([
                crispy.Field(
                    'active_accounts',
                    css_class='input-xxlarge',
                    placeholder="Select Active Account",
                ),
            ])
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '%s Subscription' % ('Edit' if is_existing else 'New'),
                account_field,
                crispy.Div(*transfer_fields),
                start_date_field,
                end_date_field,
                delay_invoice_until_field,
                plan_product_field,
                plan_edition_field,
                plan_version_field,
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
                hqcrispy.B3MultiField("Skip Auto Downgrade", 'skip_auto_downgrade'),
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

    def plan_product_field(self):
        # product type is now always commcare, but need to support old subscriptions
        is_existing = self.subscription is not None
        if is_existing:
            try:
                plan_product = self.subscription.plan_version.product_rate.product.product_type
                self.fields['plan_product'].initial = plan_product
            except (IndexError, SoftwarePlanVersion.DoesNotExist):
                plan_product = (
                    '<i class="fa fa-exclamation-triangle"></i> No Product Exists for '
                    'the Plan (update required)'
                )
            return hqcrispy.B3TextField(
                'plan_product',
                plan_product,
            )
        return hqcrispy.B3TextField(
            'plan_product',
            SoftwareProductType.COMMCARE
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
            self.subscription.account = acct
            self.subscription.save()

    @property
    def shared_keywords(self):
        return dict(
            date_start=self.cleaned_data['start_date'],
            date_end=self.cleaned_data['end_date'],
            date_delay_invoicing=self.cleaned_data['delay_invoice_until'],
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
        )

    def clean_active_accounts(self):
        transfer_account = self.cleaned_data.get('active_accounts')
        if transfer_account and transfer_account == self.subscription.account.id:
            raise ValidationError(_("Please select an account other than the "
                                    "current account to transfer to."))
        return transfer_account

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        if self.fields['domain'].required:
            domain = Domain.get_by_name(domain_name)
            if domain is None:
                raise forms.ValidationError(_("A valid project space is required."))
        return domain_name

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
                raise forms.ValidationError(mark_safe(_(
                    "Please update 'Client Contact Emails' "
                    '<strong><a href=%(link)s target="_blank">here</a></strong> '
                    "before using Billing Account <strong>%(account)s</strong>."
                ) % {
                    'link': reverse(ManageBillingAccountView.urlname, args=[account.id]),
                    'account': account.name,
                }))

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
        label=ugettext_lazy("Note"),
        required=True,
        widget=forms.Textarea,
    )
    new_plan_product = forms.ChoiceField(
        label=ugettext_lazy("Core Product"), initial=SoftwareProductType.COMMCARE,
        choices=SoftwareProductType.CHOICES,
    )
    new_plan_edition = forms.ChoiceField(
        label=ugettext_lazy("Edition"), initial=SoftwarePlanEdition.ENTERPRISE,
        choices=SoftwarePlanEdition.CHOICES,
    )
    new_plan_version = forms.CharField(label=ugettext_lazy("New Software Plan"))
    new_date_end = forms.DateField(
        label=ugettext_lazy("End Date"), widget=forms.DateInput(), required=False
    )
    service_type = forms.ChoiceField(
        label=ugettext_lazy("Type"),
        choices=SubscriptionType.CHOICES,
        initial=SubscriptionType.IMPLEMENTATION,
    )
    pro_bono_status = forms.ChoiceField(
        label=ugettext_lazy("Discounted"),
        choices=ProBonoStatus.CHOICES,
        initial=ProBonoStatus.NO,
    )
    funding_source = forms.ChoiceField(
        label=ugettext_lazy("Funding Source"),
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
                'new_plan_product',
                'new_plan_edition',
                crispy.Field(
                    'new_plan_version', css_class="input-xxlarge",
                    placeholder="Search for Software Plan"
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
            internal_change=True,
        )


class CreditForm(forms.Form):
    amount = forms.DecimalField(label="Amount (USD)")
    note = forms.CharField(required=True)
    rate_type = forms.ChoiceField(
        label=ugettext_lazy("Rate Type"),
        choices=(
            ('', 'Any'),
            ('Product', 'Product'),
            ('Feature', 'Feature'),
        ),
        required=False,
    )
    feature_type = forms.ChoiceField(required=False, label=ugettext_lazy("Feature Type"))
    adjust = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, account, subscription, *args, **kwargs):
        self.account = account
        self.subscription = subscription
        super(CreditForm, self).__init__(*args, **kwargs)

        product_choices = [('', 'Any')]
        product_choices.extend(SoftwareProductType.CHOICES)
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
            raise ValidationError(mark_safe(_(
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
        product_type = (SoftwareProductType.ANY
                        if self.cleaned_data['rate_type'] == 'Product' else None)
        feature_type = (self.cleaned_data['feature_type']
                        if self.cleaned_data['rate_type'] == 'Feature' else None)
        CreditLine.add_credit(
            amount,
            account=self.account,
            subscription=self.subscription,
            feature_type=feature_type,
            product_type=product_type,
            note=note,
            web_user=web_user,
            permit_inactive=True,
        )
        return True


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
                    'CANCEL SUBSCRIPTION',
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
            raise ValidationError(mark_safe(
                "Cannot suppress subscription. Suppress these invoices first: %s"
                % ', '.join(map(
                    lambda invoice: '<a href="{edit_url}">{name}</a>'.format(
                        edit_url=reverse(InvoiceSummaryView.urlname, args=[invoice.id]),
                        name=invoice.invoice_number,
                    ),
                    invoices
                ))
            ))


class PlanInformationForm(forms.Form):
    name = forms.CharField(max_length=80)
    description = forms.CharField(required=False)
    edition = forms.ChoiceField(choices=SoftwarePlanEdition.CHOICES)
    visibility = forms.ChoiceField(choices=SoftwarePlanVisibility.CHOICES)

    def __init__(self, plan, *args, **kwargs):
        self.plan = plan
        if plan is not None:
            kwargs['initial'] = {
                'name': plan.name,
                'description': plan.description,
                'edition': plan.edition,
                'visibility': plan.visibility,
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
        plan = SoftwarePlan(name=name,
                            description=description,
                            edition=edition,
                            visibility=visibility)
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

    feature_id = forms.CharField(
        required=False,
        label="Search for or Create Feature"
    )
    new_feature_type = forms.ChoiceField(
        required=False,
        choices=FeatureType.CHOICES,
    )
    feature_rates = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    product_id = forms.CharField(
        required=False,
        label="Search for or Create Product"
    )
    new_product_type = forms.ChoiceField(
        required=False,
        choices=SoftwareProductType.CHOICES,
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
        label="Role"
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
    )
    new_role_name = forms.CharField(
        required=False,
        max_length=256,
        label="New Role Name",
    )
    new_role_description = forms.CharField(
        required=False,
        label="New Role Description",
        widget=forms.Textarea,
    )

    def __init__(self, plan, plan_version, *args, **kwargs):
        self.plan = plan
        self.plan_version = plan_version
        self.is_update = False

        super(SoftwarePlanVersionForm, self).__init__(*args, **kwargs)

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
        self.helper.layout = crispy.Layout(
            'update_version',
            crispy.Fieldset(
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
                        InlineField('role_slug',
                                    data_bind="value: role.existing.roleSlug",
                                    css_class="input-xxlarge"),
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
            ),
            crispy.Fieldset(
                "Features",
                InlineField('feature_rates', data_bind="value: featureRates.ratesString"),
                hqcrispy.B3MultiField(
                    "Add Feature",
                    InlineField('feature_id', css_class="input-xxlarge",
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
                            css_class="btn-success",
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
            ),
            crispy.Fieldset(
                "Products",
                InlineField('product_rates', data_bind="value: productRates.ratesString"),
                hqcrispy.B3MultiField(
                    "Add Product",
                    InlineField('product_id', css_class="input-xxlarge",
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
                    InlineField(
                        'new_product_type',
                        data_bind="value: productRates.rateType",
                    ),
                    crispy.Div(
                        StrictButton(
                            "Create Product",
                            css_class="btn-success",
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
            ),
            hqcrispy.FormActions(
                StrictButton(
                    'Update Plan Version',
                    css_class='btn-primary disable-on-submit',
                    type="submit",
                ),
            )
        )

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
                'fieldName': 'feature_id',
            }
        }

    @property
    def product_rates_dict(self):
        return {
            'currentValue': self['product_rates'].value(),
            'handlerSlug': SoftwareProductRateAsyncHandler.slug,
            'select2Options': {
                'fieldName': 'product_id',
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

    @property
    @memoized
    def current_products_to_rates(self):
        if self.plan_version is not None:
            product_rate = self.plan_version.product_rate
            return {
                product_rate.product.id: product_rate
            }
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
        if feature.id not in self.current_features_to_rates.keys():
            # the plan does not have this rate yet, compare any changes to the feature's current latest rate
            # also mark the form as updated
            current_rate = feature.get_rate(default_instance=False)
            if current_rate is None:
                return new_rate
            self.is_update = True
        else:
            current_rate = self.current_features_to_rates[feature.id]
        # note: custom implementation of FeatureRate.__eq__ here...
        if not current_rate == new_rate:
            self.is_update = True
            return new_rate
        return current_rate

    def _retrieve_product_rate(self, rate_form):
        product = SoftwareProduct.objects.get(id=rate_form['product_id'].value())
        new_rate = rate_form.get_instance(product)
        if rate_form.is_new():
            # a brand new rate
            self.is_update = True
            return new_rate
        if product.id not in self.current_products_to_rates.keys():
            # the plan does not have this rate yet, compare any changes to the feature's current latest rate
            # also mark the form as updated
            current_rate = product.get_rate(default_instance=False)
            if current_rate is None:
                return new_rate
            self.is_update = True
        else:
            current_rate = self.current_products_to_rates[product.id]
        # note: custom implementation of SoftwareProductRate.__eq__ here...
        if not current_rate == new_rate:
            self.is_update = True
            return new_rate
        return current_rate

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

        required_types = dict(FeatureType.CHOICES).keys()
        feature_types = [r.feature.feature_type for r in rate_instances]
        if any([feature_types.count(t) != 1 for t in required_types]):
            raise ValidationError(_(
                "You must specify exactly one rate per feature type "
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
        rate_instances = []
        errors = ErrorList()
        if not rates:
            raise ValidationError(_("You must specify at least one product rate."))
        for rate_data in rates:
            rate_form = ProductRateForm(rate_data)
            if not rate_form.is_valid():
                errors.extend(list(self._get_errors_from_subform(rate_data['name'], rate_form)))
            else:
                rate_instances.append(self._retrieve_product_rate(rate_form))
        if errors:
            self._errors.setdefault('product_rates', errors)

        available_types = dict(SoftwareProductType.CHOICES).keys()
        product_types = [r.product.product_type for r in rate_instances]
        if any([product_types.count(p) > 1 for p in available_types]):
            raise ValidationError(_(
                "You may have at most ONE rate per product type "
                "(CommCare, CommCare Supply, etc.)"
            ))

        self.new_product_rates = rate_instances
        rate_ids = lambda x: set([r.id for r in x])
        if (not self.is_update
            and (self.plan_version is None
                 or rate_ids(rate_instances).symmetric_difference(rate_ids([self.plan_version.product_rate])))):
            self.is_update = True
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

        product_rate = self.new_product_rates[0]  # always contains one item
        product_rate.save()
        new_version.product_rate = product_rate
        new_version.save()

        for feature_rate in self.new_feature_rates:
            feature_rate.save()
            new_version.feature_rates.add(feature_rate)
        new_version.save()

        messages.success(
            request,
            'The version for %s Software Plan was successfully updated.' % new_version.plan.name
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

    class Meta:
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
    # product id will point to a  select2 field, hence the CharField here.
    product_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    rate_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        model = SoftwareProductRate
        fields = ['monthly_fee']

    def __init__(self, data=None, *args, **kwargs):
        super(ProductRateForm, self).__init__(data, *args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_tag = False
        self.helper.layout = crispy.Layout(
            crispy.HTML("""
                        <h4><span data-bind="text: name"></span>
                        <span class="label label-default"
                            style="display: inline-block; margin: 0 10px;"
                            data-bind="text: product_type"></span></h4>
                        <hr />
            """),
            crispy.Field('monthly_fee', data_bind="value: monthly_fee"),
        )

    def is_new(self):
        return not self['rate_id'].value()

    def get_instance(self, product):
        instance = self.save(commit=False)
        instance.product = product
        return instance


class EnterprisePlanContactForm(forms.Form):
    name = forms.CharField(
        label=ugettext_noop("Name")
    )
    company_name = forms.CharField(
        required=False,
        label=ugettext_noop("Company / Organization")
    )
    message = forms.CharField(
        required=False,
        label=ugettext_noop("Message"),
        widget=forms.Textarea
    )

    def __init__(self, domain, web_user, data=None, *args, **kwargs):
        self.domain = domain
        self.web_user = web_user
        super(EnterprisePlanContactForm, self).__init__(data, *args, **kwargs)
        from corehq.apps.domain.views import SelectPlanView
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = "form-horizontal"
        self.helper.layout = crispy.Layout(
            'name',
            'company_name',
            'message',
            hqcrispy.FormActions(
                StrictButton(
                    _("Request Quote"),
                    type="submit",
                    css_class="btn-primary",
                ),
                hqcrispy.LinkButton(
                    _("Select different plan"),
                    reverse(SelectPlanView.urlname, args=[self.domain]),
                    css_class="btn btn-default"
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
        html_content = render_to_string('accounting/enterprise_request_email.html', context)
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
    domain = forms.CharField(label="Project Space")

    def __init__(self, *args, **kwargs):
        super(TriggerInvoiceForm, self).__init__(*args, **kwargs)
        today = datetime.date.today()
        one_month_ago = today - relativedelta(months=1)

        self.fields['month'].initial = one_month_ago.month
        self.fields['month'].choices = MONTHS.items()
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
                'Trigger Invoice Details',
                crispy.Field('month', css_class="input-large"),
                crispy.Field('year', css_class="input-large"),
                crispy.Field('domain', css_class="input-xxlarge",
                             placeholder="Search for Project")
            ),
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
        domain = Domain.get_by_name(self.cleaned_data['domain'])
        self.clean_previous_invoices(invoice_start, invoice_end, domain.name)
        invoice_factory = DomainInvoiceFactory(
            invoice_start, invoice_end, domain, recipients=[settings.ACCOUNTS_EMAIL]
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
                    num_invoices=prev_invoices.count(),
                    invoice_list=', '.join(
                        map(
                            lambda x: '<a href="{edit_url}">{name}</a>'.format(
                                edit_url=reverse(InvoiceSummaryView.urlname,
                                                 args=(x.id,)),
                                name=x.invoice_number
                            ), prev_invoices.all()
                        )
                    ),
                )
            )

    def clean(self):
        today = datetime.date.today()
        year = int(self.cleaned_data['year'])
        month = int(self.cleaned_data['month'])

        if (year, month) >= (today.year, today.month):
            raise ValidationError('Statement period must be in the past')


class TriggerBookkeeperEmailForm(forms.Form):
    month = forms.ChoiceField(label="Invoice Month")
    year = forms.ChoiceField(label="Invoice Year")
    emails = forms.CharField(label="Email To")

    def __init__(self, *args, **kwargs):
        super(TriggerBookkeeperEmailForm, self).__init__(*args, **kwargs)
        today = datetime.date.today()

        self.fields['month'].initial = today.month
        self.fields['month'].choices = MONTHS.items()
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
                crispy.Field('emails', css_class='input-xxlarge'),
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

    def trigger_email(self):
        from corehq.apps.accounting.tasks import send_bookkeeper_email
        send_bookkeeper_email(
            month=int(self.cleaned_data['month']),
            year=int(self.cleaned_data['year']),
            emails=self.cleaned_data['emails'].split(',')
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
            (CreditAdjustmentReason.MANUAL, "Update balance directly"),
            (CreditAdjustmentReason.TRANSFER, "Take from available credit lines"),
        )
    )

    note = forms.CharField(
        required=True,
        widget=forms.Textarea,
    )

    invoice_id = forms.CharField(
        widget=forms.HiddenInput(),
    )

    adjust = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, invoice, *args, **kwargs):
        self.invoice = invoice
        super(AdjustBalanceForm, self).__init__(*args, **kwargs)
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
                css_class='modal-body',
                css_id="adjust-balance-form-%d" % invoice.id
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
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
            'account': self.invoice.subscription.account,
            'note': self.cleaned_data['note'],
            'reason': method,
            'subscription': self.invoice.subscription,
            'web_user': web_user,
        }
        if method == CreditAdjustmentReason.MANUAL:
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
                invoice=self.invoice,
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
        subscription = invoice.subscription if not invoice.is_wire else None
        super(InvoiceInfoForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'
        self.helper.form_class = 'form-horizontal'
        from corehq.apps.accounting.views import (
            EditSubscriptionView,
            ManageBillingAccountView,
        )
        if not invoice.is_wire:
            subscription_link = mark_safe(make_anchor_tag(
                reverse(EditSubscriptionView.urlname, args=(subscription.id,)),
                u'{plan_name} ({start_date} - {end_date})'.format(
                    plan_name=subscription.plan_version,
                    start_date=subscription.date_start,
                    end_date=subscription.date_end,
                )
            ))
        else:
            subscription_link = 'N/A'

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                '{} Invoice #{}'.format('Wire' if invoice.is_wire else '', invoice.invoice_number),
                hqcrispy.B3TextField(
                    'subscription',
                    subscription_link
                ),
                hqcrispy.B3TextField(
                    'project',
                    invoice.get_domain(),
                ),
                hqcrispy.B3TextField(
                    'account',
                    mark_safe(
                        '<a href="%(account_link)s">'
                        '%(account_name)s'
                        '</a>' % {
                            'account_link': reverse(
                                ManageBillingAccountView.urlname,
                                args=(invoice.account.id,)
                            ),
                            'account_name': invoice.account.name,
                        }
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
                ),
            ),
        )


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
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'resend_email',
                        'Send Email',
                        css_class='disable-on-submit',
                        data_loading_text='Submitting...',
                    ),
                    crispy.Button(
                        'close',
                        'Close',
                        css_class='disable-on-submit',
                        data_dismiss='modal',
                    ),
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
        else:
            record = BillingRecord.generate_record(self.invoice)
        record.send_email(contact_emails=contact_emails)


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
                mark_safe('<i class="fa fa-plus"></i> %s' % "Add Admin"),
                css_class="btn-success disable-on-submit",
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
