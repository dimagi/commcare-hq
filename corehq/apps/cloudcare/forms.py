from django import forms


class CloudCareControlsForm(forms.Form):

    mobile_username = forms.CharField(required=False)
    mobile_password = forms.CharField(widget=forms.PasswordInput(), required=False)

    preview_mode = forms.BooleanField(required=False)
