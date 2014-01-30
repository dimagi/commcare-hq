import datetime
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django import forms
from django.forms.util import ErrorList
from crispy_forms.bootstrap import FormActions, StrictButton, InlineField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import *

from dimagi.utils.decorators.memoized import memoized
from django_prbac import arbitrary as role_gen

from corehq.apps.accounting.async_handlers import FeatureRateAsyncHandler, Select2RateAsyncHandler
from corehq.apps.accounting.utils import fmt_feature_rate_dict
from corehq.apps.hqwebapp.crispy import BootstrapMultiField
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.apps.accounting.models import (BillingContactInfo, Currency, SoftwarePlanVersion, BillingAccount,
                                           Subscription, Subscriber, CreditLine, SoftwareProductRate,
                                           FeatureRate, SoftwarePlanEdition, SoftwarePlanVisibility,
                                           BillingAccountAdmin, SoftwarePlan, Feature, FeatureType)


class BillingAccountForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID", required=False)
    currency = forms.ChoiceField(label="Currency")

    billing_account_admins = forms.CharField(label='Billing Account Admins', required=False)
    first_name = forms.CharField(label='First Name', required=False)
    last_name = forms.CharField(label='Last Name', required=False)
    company_name = forms.CharField(label='Company Name', required=False)
    phone_number = forms.CharField(label='Phone Number', required=False)
    address_line_1 = forms.CharField(label='Address Line 1')
    address_line_2 = forms.CharField(label='Address Line 2', required=False)
    city = forms.CharField()
    region = forms.CharField(label="State/Province/Region")
    postal_code = forms.CharField(label="Postal Code")
    country = forms.CharField()

    def __init__(self, account, *args, **kwargs):
        if account is not None:
            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            kwargs['initial'] = {
                'name': account.name,
                'salesforce_account_id': account.salesforce_account_id,
                'currency': account.currency.code,
                'billing_account_admins':
                ', '.join([admin.web_user for admin in account.billing_admins.all()]),
                'first_name': contact_info.first_name,
                'last_name': contact_info.last_name,
                'company_name': contact_info.company_name,
                'phone_number': contact_info.phone_number,
                'address_line_1': contact_info.first_line,
                'address_line_2': contact_info.second_line,
                'city': contact_info.city,
                'region': contact_info.state_province_region,
                'postal_code': contact_info.postal_code,
                'country': contact_info.country,
            }
        else:
            kwargs['initial'] = {
                'currency': Currency.get_default().code,
            }
        super(BillingAccountForm, self).__init__(*args, **kwargs)
        if account is None:
            self.fields['address_line_1'].required = False
            self.fields['city'].required = False
            self.fields['region'].required = False
            self.fields['postal_code'].required = False
            self.fields['country'].required = False
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            'Basic Information',
                'name',
                'salesforce_account_id',
                'currency',
            ),
            Fieldset(
            'Contact Information',
                'billing_account_admins',
                'first_name',
                'last_name',
                'company_name',
                'phone_number',
                'address_line_1',
                'address_line_2',
                'city',
                'region',
                'postal_code',
                'country',
            ) if account is not None else None,
            FormActions(
                ButtonHolder(
                    Submit('account', 'Update Account' if account is not None else 'Add New Account')
                )
            )
        )

    def clean_billing_account_admins(self):
        billing_account_admins = self.cleaned_data['billing_account_admins']
        if billing_account_admins != '':
            invalid_emails = []
            for email in billing_account_admins.split(','):
                email_no_whitespace = email.strip()
                if WebUser.get_by_username(email_no_whitespace) is None:
                    invalid_emails.append("'%s'" % email_no_whitespace)
            if len(invalid_emails) != 0:
                raise ValidationError("Invalid emails: %s" % ', '.join(invalid_emails))
        return billing_account_admins

    def create_account(self):
        name = self.cleaned_data['name']
        salesforce_account_id = self.cleaned_data['salesforce_account_id']
        currency, _ = Currency.objects.get_or_create(code=self.cleaned_data['currency'])
        account = BillingAccount(name=name,
                                 salesforce_account_id=salesforce_account_id,
                                 currency=currency)
        account.save()
        return account

    def update_account_and_contacts(self, account):
        account.name = self.cleaned_data['name']
        account.salesforce_account_id = self.cleaned_data['salesforce_account_id']
        account.currency, _ = Currency.objects.get_or_create(code=self.cleaned_data['currency'])
        for web_user_email in self.cleaned_data['billing_account_admins'].split(','):
            admin, _ = BillingAccountAdmin.objects.get_or_create(web_user=web_user_email)
            account.billing_admins.add(admin)
        account.save()

        contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
        contact_info.first_name = self.cleaned_data['first_name']
        contact_info.last_name = self.cleaned_data['last_name']
        contact_info.company_name = self.cleaned_data['company_name']
        contact_info.phone_number = self.cleaned_data['phone_number']
        contact_info.first_line = self.cleaned_data['address_line_1']
        contact_info.second_line = self.cleaned_data['address_line_2']
        contact_info.city = self.cleaned_data['city']
        contact_info.state_province_region = self.cleaned_data['region']
        contact_info.postal_code = self.cleaned_data['postal_code']
        contact_info.country = self.cleaned_data['country']
        contact_info.save()


class SubscriptionForm(forms.Form):
    start_date = forms.DateField(label="Start Date", widget=forms.DateInput())
    end_date = forms.DateField(label="End Date", widget=forms.DateInput(), required=False)
    delay_invoice_until = forms.DateField(label="Delay Invoice Until", widget=forms.DateInput(), required=False)
    plan_version = forms.ChoiceField(label="Plan Version")
    domain = forms.CharField(max_length=25)
    salesforce_contract_id = forms.CharField(label="Salesforce Contract ID", max_length=80, required=False)

    def __init__(self, subscription, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)

        css_class = {'css_class': 'date-picker'}
        disabled = {'disabled': 'disabled'}

        start_date_kwargs = dict(**css_class)
        end_date_kwargs = dict(**css_class)
        delay_invoice_until_kwargs = dict(**css_class)
        plan_kwargs = dict()
        domain_kwargs = dict()

        self.fields['plan_version'].choices = [(plan_version.id, str(plan_version))
                                               for plan_version in SoftwarePlanVersion.objects.all()]
        if subscription is not None:
            self.fields['start_date'].initial = subscription.date_start
            self.fields['end_date'].initial = subscription.date_end
            self.fields['delay_invoice_until'].initial = subscription.date_delay_invoicing
            self.fields['plan_version'].initial = subscription.plan_version.id
            self.fields['domain'].initial = subscription.subscriber.domain
            self.fields['salesforce_contract_id'].initial = subscription.salesforce_contract_id
            if (subscription.date_start is not None
                and subscription.date_start <= datetime.date.today()):
                start_date_kwargs.update(disabled)
                self.fields['start_date'].required = False
            if (subscription.date_end is not None
                and subscription.date_end <= datetime.date.today()):
                end_date_kwargs.update(disabled)
            if (subscription.date_delay_invoicing is not None
                and subscription.date_delay_invoicing <= datetime.date.today()):
                delay_invoice_until_kwargs.update(disabled)
            plan_kwargs.update(disabled)
            self.fields['plan_version'].required = False
            domain_kwargs.update(disabled)
            self.fields['domain'].required = False
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            '%s Subscription' % ('Edit' if subscription is not None else 'New'),
                Field('start_date', **start_date_kwargs),
                Field('end_date', **end_date_kwargs),
                Field('delay_invoice_until', **delay_invoice_until_kwargs),
                Field('plan_version', **plan_kwargs),
                Field('domain', **domain_kwargs),
                'salesforce_contract_id',
            ),
            FormActions(
                ButtonHolder(
                    Submit('set_subscription',
                           '%s Subscription' % ('Update' if subscription is not None else 'Create'))
                )
            )
        )

    def clean_domain(self):
        domain_name = self.cleaned_data['domain']
        if self.fields['domain'].required:
            domain = Domain.get_by_name(domain_name)
            if domain is None:
                raise forms.ValidationError("A valid project space is required.")
        return domain_name

    def create_subscription(self, account_id):
        account = BillingAccount.objects.get(id=account_id)
        date_start = self.cleaned_data['start_date']
        date_end = self.cleaned_data['end_date']
        date_delay_invoicing = self.cleaned_data['delay_invoice_until']
        plan_version_id = self.cleaned_data['plan_version']
        domain = self.cleaned_data['domain']
        subscription = Subscription(account=account,
                                    date_start=date_start,
                                    date_end=date_end,
                                    date_delay_invoicing=date_delay_invoicing,
                                    plan_version=SoftwarePlanVersion.objects.get(id=plan_version_id),
                                    salesforce_contract_id=self.cleaned_data['salesforce_contract_id'],
                                    subscriber=Subscriber.objects.get_or_create(domain=domain,
                                                                                organization=None)[0])
        subscription.save()
        return subscription

    def update_subscription(self, subscription):
        if self.fields['start_date'].required:
            subscription.date_start = self.cleaned_data['start_date']
        if subscription.date_end is None or subscription.date_end > datetime.date.today():
            subscription.date_end = self.cleaned_data['end_date']
        if (subscription.date_delay_invoicing is None
            or subscription.date_delay_invoicing > datetime.date.today()):
            subscription.date_delay_invoicing = self.cleaned_data['delay_invoice_until']
        subscription.salesforce_contract_id = self.cleaned_data['salesforce_contract_id']
        subscription.save()


class CreditForm(forms.Form):
    amount = forms.DecimalField()
    note = forms.CharField(required=False)
    rate_type = forms.ChoiceField()
    product = forms.ChoiceField(required=False)
    feature = forms.ChoiceField(label="Rate", required=False)

    def __init__(self, id, is_account, *args, **kwargs):
        super(CreditForm, self).__init__(*args, **kwargs)
        if not kwargs:
            self.fields['product'].choices = self.get_product_choices(id, is_account)
            self.fields['feature'].choices = self.get_feature_choices(id, is_account)
            self.fields['rate_type'].choices = self.get_rate_type_choices(self.fields['product'].choices,
                                                                          self.fields['feature'].choices)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            'Adjust %s Level Credit' % ('Account' if is_account else 'Subscription'),
                'amount',
                'note',
                Field('rate_type', data_bind="value: rateType"),
                Div('product', data_bind="visible: showProduct"),
                Div('feature', data_bind="visible: showFeature"),
            ),
            FormActions(
                ButtonHolder(
                    Submit('adjust_credit', 'Update Credit')
                )
            )
        )

    def get_subscriptions(self, id, is_account):
        return Subscription.objects.filter(account=BillingAccount.objects.get(id=id))\
            if is_account else [Subscription.objects.get(id=id)]

    def get_product_choices(self, id, is_account):
        subscriptions = self.get_subscriptions(id, is_account)
        product_rate_sets = [sub.plan_version.product_rates for sub in subscriptions]
        products = set()
        for product_rate_set in product_rate_sets:
            for product_rate in product_rate_set.all():
                products.add(product_rate.product)
        return [(product.id, product.name) for product in products]

    def get_feature_choices(self, id, is_account):
        subscriptions = self.get_subscriptions(id, is_account)
        feature_rate_sets = [sub.plan_version.feature_rates for sub in subscriptions]
        features = set()
        for feature_rate_set in feature_rate_sets:
            for feature_rate in feature_rate_set.all():
                features.add(feature_rate.feature)
        return [(feature.id, feature.name) for feature in features]

    def get_rate_type_choices(self, product_choices, feature_choices):
        choices = [('Any', 'Any')]
        if len(product_choices) != 0:
            choices.append(('Product', 'Product'))
        if len(feature_choices) != 0:
            choices.append(('Feature', 'Feature'))
        return choices

    def adjust_credit(self, account=None, subscription=None):
        amount = self.cleaned_data['amount']
        note = self.cleaned_data['note']

        def get_account_for_rate():
            return account if account is not None else subscription.account

        def add_product_rate():
            CreditLine.add_rate_credit(amount, get_account_for_rate(),
                                       product_rate=SoftwareProductRate.objects.get(id=self.cleaned_data['product']),
                                       subscription=subscription,
                                       note=note)

        def add_feature_rate():
            CreditLine.add_rate_credit(amount, get_account_for_rate(),
                                       feature_rate=FeatureRate.objects.get(id=self.cleaned_data['feature']),
                                       subscription=subscription,
                                       note=note)

        def add_account_level():
            CreditLine.add_account_credit(amount, account,
                                          note=note)

        def add_subscription_level():
            CreditLine.add_subscription_credit(amount, subscription,
                                               note=note)

        if self.cleaned_data['rate_type'] == 'Product':
            add_product_rate()
        elif self.cleaned_data['rate_type'] == 'Feature':
            add_feature_rate()
        elif account is not None:
            add_account_level()
        elif subscription is not None:
            add_subscription_level()
        else:
            raise ValueError('invalid credit adjustment')


class CancelForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(CancelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        cancel_subscription_button = Button('cancel_subscription', 'CANCEL SUBSCRIPTION', css_class="btn-danger")
        cancel_subscription_button.input_type = 'submit'
        self.helper.layout = Layout(
            ButtonHolder(
                cancel_subscription_button
            )
        )


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
        self.helper.layout = Layout(
            Fieldset(
            'Plan Information',
                'name',
                'description',
                'edition',
                'visibility',
            ),
            FormActions(
                ButtonHolder(
                    Submit('plan_information',
                           '%s Software Plan' % ('Update' if plan is not None else 'Create'))
                )
            )
        )

    def clean_name(self):
        name = self.cleaned_data['name']
        if (len(SoftwarePlan.objects.filter(name=name)) != 0
            and (self.plan is None or self.plan.name != name)):
            raise ValidationError('Name already taken.  Please enter a new name.')
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

    def update_plan(self, plan):
        plan.name = self.cleaned_data['name']
        plan.description = self.cleaned_data['description']
        plan.edition = self.cleaned_data['edition']
        plan.visibility = self.cleaned_data['visibility']
        plan.save()
