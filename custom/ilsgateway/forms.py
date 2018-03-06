from __future__ import absolute_import
from __future__ import unicode_literals
from django import forms
from django.utils.translation import ugettext as _


class SupervisionDocumentForm(forms.Form):
    document = forms.FileField(
        label=_('Upload a file'),
    )


class ILSConfigForm(forms.Form):
    enabled = forms.BooleanField(label="Enable ILSGateway integration?", required=False)
