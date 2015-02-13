from django.forms import forms
from django.utils.translation import ugettext as _


class SupervisionDocumentForm(forms.Form):
    document = forms.FileField(
        label=_('Upload a file'),
    )
