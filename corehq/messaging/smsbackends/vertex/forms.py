from corehq.apps.sms.forms import BackendForm
from django import forms
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy, ugettext as _


class VertexBackendForm(BackendForm):
    username = forms.CharField(
        label=ugettext_lazy("username"),
        required=True,
    )
    password = forms.CharField(
        label=ugettext_lazy("pass"),
        required=True,
    )
    senderid = forms.CharField(
        label=ugettext_lazy("senderid"),
        required=True,
    )
    response = forms.ChoiceField(
        label=ugettext_lazy("response"),
        required=True,
        choices=(('Y', 'Yes'), ('N', 'No')),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Vertex Settings"),
            'username',
            'password',
            'senderid',
            'response',
        )
