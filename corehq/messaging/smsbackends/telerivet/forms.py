from corehq.apps.sms.forms import BackendForm
from corehq.apps.style import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Field, Div, HTML
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from django.forms.forms import Form
from django.utils.translation import ugettext as _, ugettext_lazy


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
        from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
        value = self.cleaned_data['webhook_secret']
        backend = SQLTelerivetBackend.by_webhook_secret(value)
        if backend and backend.pk != self._cchq_backend_id:
            raise ValidationError(_("Already in use."))
        return value


class TelerivetOutgoingSMSForm(Form):
    api_key = TrimmedCharField(
        label=ugettext_lazy("API Key"),
        required=True
    )
    project_id = TrimmedCharField(
        label=ugettext_lazy("Project ID"),
        required=True
    )
    phone_id = TrimmedCharField(
        label=ugettext_lazy("Phone ID"),
        required=True
    )

    def __init__(self, *args, **kwargs):
        super(TelerivetOutgoingSMSForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-1'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.layout = Layout(
            Fieldset(
                _("Telerivet Outgoing SMS Settings"),
                Field(
                    'api_key',
                    ng_model='apiKey',
                ),
                Field(
                    'project_id',
                    ng_model='projectId',
                ),
                Field(
                    'phone_id',
                    ng_model='phoneId',
                ),
            )
        )


class TelerivetPhoneNumberForm(Form):
    test_phone_number = TrimmedCharField(
        required=True
    )

    def __init__(self, *args, **kwargs):
        super(TelerivetPhoneNumberForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-2 col-md-1'
        self.helper.field_class = 'col-sm-4 col-md-3'
        self.helper.layout = Layout(
            Fieldset(
                _("Send a Test SMS"),
                hqcrispy.B3MultiField(
                    _("Test Phone Number"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'test_phone_number',
                            ng_model='testPhoneNumber'
                        ),
                        css_class="col-sm-8"
                    ),
                    Div(
                        HTML('<button class="btn btn-success" ng-click="sendTestSMS();">%s</button>' %
                             _('Send'))
                    )
                )
            )
        )
