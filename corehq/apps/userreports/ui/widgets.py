import json
from django import forms


class JsonWidget(forms.Textarea):

    def render(self, name, value, attrs=None):
        if isinstance(value, basestring):
            # It's probably invalid JSON
            return super(JsonWidget, self).render(name, value, attrs)

        return super(JsonWidget, self).render(name, json.dumps(value, indent=2), attrs)
