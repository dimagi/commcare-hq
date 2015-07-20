from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _, ugettext_lazy
from crispy_forms import layout as crispy

class TelerivetBackendForm(BackendForm):
    api_key = TrimmedCharField(
        label=ugettext_lazy("API Key"),
    )
    project_id = TrimmedCharField(
        label=ugettext_lazy("Project ID"),
    )
    phone_id = TrimmedCharField(
        label=ugettext_lazy("Phone ID"),
    )
    webhook_secret = TrimmedCharField(
        label=ugettext_lazy("Webhook Secret"),
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Telerivet (Android) Settings"),
            'api_key',
            'project_id',
            'phone_id',
            'webhook_secret',
        )

    def clean_webhook_secret(self):
        # Circular import
        from corehq.apps.telerivet.models import TelerivetBackend
        value = self.cleaned_data.get("webhook_secret", None)
        backend = TelerivetBackend.by_webhook_secret(value)
        if backend is not None and backend._id != self._cchq_backend_id:
            raise ValidationError(_("Already in use."))
        return value

