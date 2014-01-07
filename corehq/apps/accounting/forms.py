from datetime import datetime
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Fieldset, Layout, Submit
from django import forms
from django.forms.extras.widgets import SelectDateWidget

from corehq.apps.accounting.models import Currency
from corehq.apps.users.models import WebUser


class BillingAccountForm(forms.Form):
    client_name = forms.CharField(label="Client Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID")
    currency = forms.ChoiceField(label="Currency")
    autosend_invoices = forms.BooleanField(label="Send invoices automatically")
    web_user_contact = forms.ChoiceField(label="Billing Contact", required=False)

    def __init__(self, account, *args, **kwargs):
        if account is not None:
            kwargs['initial'] = {'client_name': account.name,
                                 'salesforce_account_id': account.salesforce_account_id,
                                 'currency': account.currency.code,
                                 'web_user_contact': account.web_user_contact,
                                 }
        super(BillingAccountForm, self).__init__(*args, **kwargs)
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
        self.fields['web_user_contact'].choices =\
            [('', '')] + [(web_user.username, web_user.username) for web_user in WebUser.all()]
        self.helper = FormHelper()
        self.helper.layout = Layout(
            FormActions(
                Fieldset(
                '%s Billing Account' % ('Manage' if account is not None else 'New'),
                    'client_name',
                    'salesforce_account_id',
                    'currency',
                    'autosend_invoices',
                    'web_user_contact',
                ),
                ButtonHolder(
                    Submit('submit', 'Update Account' if account is not None else 'Add New Account')
                )
            )
        )


class SubscriptionForm(forms.Form):
    start_date = forms.DateField(label="Start Date", widget=SelectDateWidget())
    end_date = forms.DateField(label="End Date", widget=SelectDateWidget())
    delay_invoice_until = forms.DateField(label="Delay Invoice Until", widget=SelectDateWidget())
    #line_items = forms.SelectMultiple(choices=(('a', 'b')))
    note = forms.CharField(required=False)

    def __init__(self, subscription, *args, **kwargs):
        super(SubscriptionForm, self).__init__(*args, **kwargs)
        if subscription is not None:
            self.fields['start_date'].initial = subscription.date_start
            self.fields['end_date'].initial = subscription.date_end
            self.fields['delay_invoice_until'].initial = subscription.date_delay_invoicing
        self.helper = FormHelper()
        self.helper.layout = Layout(
            FormActions(
                Fieldset(
                '%s Subscription' % ('Edit' if subscription is not None else 'New'),
                    'start_date',
                    'end_date',
                    'delay_invoice_until',
                    'note',
                ),
                ButtonHolder(
                    Submit('submit', 'Submit')
                )
            )
        )
