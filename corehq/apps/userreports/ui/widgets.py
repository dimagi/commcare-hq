from __future__ import absolute_import
import json
from django import forms
import six

from corehq.util.python_compatibility import soft_assert_type_text


class JsonWidget(forms.Textarea):

    def render(self, name, value, attrs=None, renderer=None):
        if isinstance(value, six.string_types):
            soft_assert_type_text(value)
            # It's probably invalid JSON
            return super(JsonWidget, self).render(name, value, attrs, renderer)

        return super(JsonWidget, self).render(name, json.dumps(value, indent=2), attrs, renderer)
