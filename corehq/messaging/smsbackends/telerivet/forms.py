from corehq.apps.sms.forms import BackendForm
from corehq.apps.sms.util import validate_phone_number
from corehq.apps.style import crispy as hqcrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton, FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, HTML
from dimagi.utils.django.fields import TrimmedCharField
from django.core.exceptions import ValidationError
from django.forms.fields import ChoiceField
from django.forms.forms import Form
from django.utils.translation import ugettext as _, ugettext_lazy


def get_rmi_error_placeholder(error_name):
    return Div(
        HTML('<span class="help-block"><strong ng-bind="%s"></strong></span>' % error_name),
        ng_show=error_name,
    )


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
            Div(
                hqcrispy.B3MultiField(
                    _("API Key"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'api_key',
                            ng_model='apiKey'
                        )
                    ),
                    get_rmi_error_placeholder('apiKeyError'),
                    ng_class="{'has-error': apiKeyError}"
                ),
                hqcrispy.B3MultiField(
                    _("Project ID"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'project_id',
                            ng_model='projectId'
                        )
                    ),
                    get_rmi_error_placeholder('projectIdError'),
                    ng_class="{'has-error': projectIdError}"
                ),
                hqcrispy.B3MultiField(
                    _("Phone ID"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'phone_id',
                            ng_model='phoneId'
                        )
                    ),
                    get_rmi_error_placeholder('phoneIdError'),
                    ng_class="{'has-error': phoneIdError}"
                )
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
            Div(
                hqcrispy.B3MultiField(
                    _("Test Phone Number"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'test_phone_number',
                            ng_model='testPhoneNumber'
                        )
                    ),
                    get_rmi_error_placeholder('testPhoneNumberError'),
                    Div(
                        StrictButton(
                            _("Send"),
                            id='id_send_sms_button',
                            css_class='btn btn-success',
                            ng_click='sendTestSMS();'
                        )
                    ),
                    ng_class="{'has-error': testPhoneNumberError}"
                )
            )
        )

    def clean_test_phone_number(self):
        value = self.cleaned_data.get('test_phone_number')
        validate_phone_number(value)
        return value


class FinalizeGatewaySetupForm(Form):
    YES = 'Y'
    NO = 'N'

    YES_NO_CHOICES = (
        (YES, ugettext_lazy("Yes")),
        (NO, ugettext_lazy("No")),
    )

    name = TrimmedCharField(
        label=ugettext_lazy("Name"),
        required=True
    )
    set_as_default = ChoiceField(
        label=ugettext_lazy("Set as default gateway"),
        choices=YES_NO_CHOICES,
        required=True
    )

    def __init__(self, *args, **kwargs):
        super(FinalizeGatewaySetupForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.label_class = 'col-sm-3 col-md-2'
        self.helper.field_class = 'col-sm-3 col-md-2'
        self.helper.layout = Layout(
            Div(
                hqcrispy.B3MultiField(
                    _("Name"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'name',
                            ng_model='name'
                        )
                    ),
                    get_rmi_error_placeholder('nameError'),
                    ng_class="{'has-error': nameError}"
                ),
                hqcrispy.B3MultiField(
                    _("Set as default gateway"),
                    Div(
                        hqcrispy.MultiInlineField(
                            'set_as_default',
                            ng_model='setAsDefault'
                        )
                    ),
                    get_rmi_error_placeholder('setAsDefaultError'),
                    ng_class="{'has-error': setAsDefaultError}"
                ),
                FormActions(
                    StrictButton(
                        _("Finish"),
                        id="id_create_backend",
                        css_class='btn-primary',
                        ng_click='createBackend();'
                    )
                )
            )
        )
