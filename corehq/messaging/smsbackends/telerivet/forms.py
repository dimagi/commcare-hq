from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _, ugettext_noop
from crispy_forms import layout as crispy

class TelerivetBackendForm(BackendForm):
    api_key = TrimmedCharField(
        label=ugettext_noop("API Key"),
    )
    project_id = TrimmedCharField(
        label=ugettext_noop("Project ID"),
    )
    phone_id = TrimmedCharField(
        label=ugettext_noop("Phone ID"),
    )
    webhook_secret = TrimmedCharField(
        label=ugettext_noop("Webhook Secret"),
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
        from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
        value = self.cleaned_data['webhook_secret']
        backend = SQLTelerivetBackend.by_webhook_secret(value)
        if backend and backend.pk != self._cchq_backend_id:
            raise ValidationError(_("Already in use."))
        return value
