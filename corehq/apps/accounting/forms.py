from django import forms
from corehq.apps.accounting.models import Currency


class BillingAccountForm(forms.Form):
    client_name = forms.CharField(label="Client Name")
    salesforce_id = forms.CharField(label="Salesforce ID")
    currency = forms.ChoiceField(label="Currency")
    autosend_invoices = forms.BooleanField(label="Send invoices automatically")

    def __init__(self, *args, **kwargs):
        super(BillingAccountForm, self).__init__(*args, **kwargs)
        self.fields['currency'].choices =\
            [(cur.code, cur.code) for cur in Currency.objects.order_by('code')]
