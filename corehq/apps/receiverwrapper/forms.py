from django import forms

class FormRepeaterForm(forms.Form):
    url = forms.URLField(required=True, label='URL to forward to',
                         help_text='Please enter the full url, like http://www.example.com/forwarding/',
                         widget=forms.TextInput(attrs={"class": "url"}))
