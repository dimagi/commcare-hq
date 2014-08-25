from django import forms


class GenericRepeaterForm(forms.Form):
    url = forms.URLField(
        required=True,
        label='URL to forward to',
        help_text='Please enter the full url, like http://www.example.com/forwarding/',
        widget=forms.TextInput(attrs={"class": "url"})
    )


class FormRepeaterForm(GenericRepeaterForm):
    exclude_device_reports = forms.BooleanField(
        required=False,
        label='Exclude device reports',
        initial=True
    )