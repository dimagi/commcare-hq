from __future__ import absolute_import
from django.forms.fields import CharField


class TrimmedCharField(CharField):
    def clean(self, value):
        if value is not None:
            value = value.strip()
        return super(TrimmedCharField, self).clean(value)

