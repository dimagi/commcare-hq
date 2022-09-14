from django import forms


class RawJSONForm(forms.Form):
    raw_json = forms.JSONField(required=True, initial=dict)
