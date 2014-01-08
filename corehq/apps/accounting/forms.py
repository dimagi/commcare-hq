from datetime import datetime
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Fieldset, Layout, Submit
from django import forms
from django.forms.extras.widgets import SelectDateWidget

from corehq.apps.accounting.models import Currency
from corehq.apps.users.models import WebUser


class BillingAccountForm(forms.Form):
    name = forms.CharField(label="Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID")
    currency = forms.ChoiceField(label="Currency")

    def __init__(self, account, *args, **kwargs):
        if account is not None:
            kwargs['initial'] = {'name': account.name,
                                 'salesforce_account_id': account.salesforce_account_id,
                                 'currency': account.currency.code,
                                 }
        super(BillingAccountForm, self).__init__(*args, **kwargs)
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
        self.helper = FormHelper()
        self.helper.layout = Layout(
            FormActions(
                Fieldset(
                'Account',
                    'name',
                    'salesforce_account_id',
                    'currency',
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
