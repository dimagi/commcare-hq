from django import forms


class BillingAccountForm(forms.Form):
    # salesforce ID (text input)
    # currency dropdown
    # send invoices automatically (checkbox)
    client_name = forms.CharField("Filter Option", required=False)
