from django import forms


class TransifexOrganizationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(TransifexOrganizationForm, self).__init__(*args, **kwargs)
        self.initial['api_token'] = self.instance.plaintext_api_token
