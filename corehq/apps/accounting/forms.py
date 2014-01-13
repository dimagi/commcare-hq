import datetime
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Fieldset, Layout, Submit, Field
from django import forms
from django.forms.extras.widgets import SelectDateWidget

from corehq.apps.accounting.models import Currency, BillingContactInfo
from corehq.apps.users.models import WebUser


class BillingAccountForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID")
    currency = forms.ChoiceField(label="Currency")

    billing_account_admins = forms.CharField()
    first_name = forms.CharField(label='First Name')
    last_name = forms.CharField(label='Last Name')
    company_name = forms.CharField(label='Company Name')
    phone_number = forms.CharField(label='Phone Number')
    address_line_1 = forms.CharField(label='Address Line 1')
    address_line_2 = forms.CharField(label='Address Line 2')
    city = forms.CharField()
    region = forms.CharField(label="State/Province/Region")
    postal_code = forms.CharField(label="Postal Code")
    country = forms.CharField()

    def __init__(self, account, *args, **kwargs):
        if account is not None:
            contact_info, _ = BillingContactInfo.objects.get_or_create(account=account)
            kwargs['initial'] = {'name': account.name,
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
        super(BillingAccountForm, self).__init__(*args, **kwargs)
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
                    Submit('submit', 'Update Account' if account is not None else 'Add New Account')
                )
            )
        )


class SubscriptionForm(forms.Form):
    start_date = forms.DateField(label="Start Date", widget=forms.DateInput())
    end_date = forms.DateField(label="End Date", widget=forms.DateInput())
    delay_invoice_until = forms.DateField(label="Delay Invoice Until", widget=forms.DateInput())

    def __init__(self, subscription, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)

        css_class = dict(css_class='date-picker')
        disabled = dict(disabled='disabled')

        start_date_kwargs = dict(**css_class)
        end_date_kwargs = dict(**css_class)
        delay_invoice_until_kwargs = dict(**css_class)

        if subscription is not None:
            self.fields['start_date'].initial = subscription.date_start
            self.fields['end_date'].initial = subscription.date_end
            self.fields['delay_invoice_until'].initial = subscription.date_delay_invoicing
            if subscription.date_start is not None \
                and subscription.date_start <= datetime.date.today():
                start_date_kwargs.update(disabled)
            if subscription.date_end is not None \
                and subscription.date_end <= datetime.date.today():
                end_date_kwargs.update(disabled)
            if subscription.date_delay_invoicing is not None \
                and subscription.date_delay_invoicing <= datetime.date.today():
                delay_invoice_until_kwargs.update(disabled)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
            '%s Subscription' % ('Edit' if subscription is not None else 'New'),
                Field('start_date', **start_date_kwargs),
                Field('end_date', **end_date_kwargs),
                Field('delay_invoice_until', **delay_invoice_until_kwargs),
            ),
            FormActions(
                ButtonHolder(
                    Submit('submit', 'Submit')
                )
            )
        )
