from django.forms.fields import *
from corehq.apps.sms.forms import BackendForm
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

class TelerivetBackendForm(BackendForm):
    api_key = TrimmedCharField()
    project_id = TrimmedCharField()
    phone_id = TrimmedCharField()
    webhook_secret = TrimmedCharField()

    def clean_webhook_secret(self):
        # Circular import
        from corehq.apps.telerivet.models import TelerivetBackend
        value = self.cleaned_data.get("webhook_secret", None)
        backend = TelerivetBackend.by_webhook_secret(value)
        if backend is not None and backend._id != self._cchq_backend_id:
            raise ValidationError(_("Already in use."))
        return value

