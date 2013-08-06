import json
from django.core.exceptions import ValidationError
from django.forms import forms, fields

class PrescriptionForm(forms.Form):
    domain = fields.CharField()
    type = fields.CharField()
    start = fields.DateTimeField()
    end = fields.DateTimeField()
    params = fields.CharField(required=False)

    def clean_params(self):
        try:
            params = json.loads(self.cleaned_data['params']) if self.cleaned_data['params'] else {}
        except ValueError:
            raise ValidationError('Message has to be a JSON obj')
        if not isinstance(params, dict):
            raise ValidationError('Message has to be a JSON obj')
        return params
