from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from crispy_forms import layout as crispy
from django.utils.translation import ugettext_lazy, ugettext as _


class VertexBackendForm(BackendForm):
    username = TrimmedCharField(
        label=ugettext_lazy("username"),
        required=True,
    )
    password = TrimmedCharField(
        label=ugettext_lazy("password"),
        required=True,
    )
    senderid = TrimmedCharField(
        label=ugettext_lazy("senderid"),
        required=True,
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Vertex Settings"),
            'username',
            'password',
            'senderid',
        )
