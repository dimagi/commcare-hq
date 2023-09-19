from crispy_forms import layout as crispy
from django.forms.fields import BooleanField
from django.utils.translation import gettext as _, gettext_noop, gettext_lazy

from corehq.apps.email.forms import BackendForm


class AWSBackendForm(BackendForm):

    use_tracking_headers = BooleanField(
        required=False,
        label=gettext_noop("Use Tracking Headers"),
        help_text=gettext_lazy("If selected, headers will be appended in the outgoing mails for tracking. "
                               "Use key generated in HQ in the AWS SNS settings. Key can be found by selecting "
                               "the gateway from the list."
                               )
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("AWS Settings"),
            'use_tracking_headers',
        )
