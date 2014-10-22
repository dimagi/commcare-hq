import json
from django import forms


class JsonWidget(forms.Textarea):

    def render(self, name, value, attrs=None):
        return super(JsonWidget, self).render(name, json.dumps(value, indent=2), attrs)
