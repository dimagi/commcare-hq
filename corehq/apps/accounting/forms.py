from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import ButtonHolder, Div, Fieldset, HTML, Layout, Submit
from django import forms
from corehq.apps.accounting.models import Currency


class BillingAccountForm(forms.Form):
    client_name = forms.CharField(label="Client Name")
    salesforce_account_id = forms.CharField(label="Salesforce ID")
    currency = forms.ChoiceField(label="Currency")
    autosend_invoices = forms.BooleanField(label="Send invoices automatically")

    def __init__(self, account, *args, **kwargs):
        kwargs['initial'] = {'client_name': account.name,
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
                'Manage Billing Account',
                    'client_name',
                    'salesforce_account_id',
                    'currency',
                    'autosend_invoices',
                ),
                ButtonHolder(
                    Submit('submit', 'Create Mobile Worker')
                )
            )
        )
