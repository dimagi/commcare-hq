from django import forms


class BillingAccountForm(forms.Form):
    client_name = forms.CharField(label="Client Name")
    salesforce_id = forms.CharField(label="Salesforce ID")
    currency = forms.ChoiceField(label="Currency")
    autosend_invoices = forms.BooleanField(label="Send invoices automatically")
