from crispy_forms import layout as crispy
from django.utils.translation import gettext as _

from corehq.apps.email.forms import BackendForm


class AWSBackendForm(BackendForm):

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("AWS Settings"),
        )
