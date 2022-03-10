from django.core.exceptions import ValidationError
from django.forms.fields import BooleanField, ChoiceField
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from crispy_forms import layout as crispy

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.reminders.forms import RecordListField
from corehq.apps.sms.forms import BackendForm

from .form_handling import form_clean_url


class HttpBackendForm(BackendForm):
    url = TrimmedCharField(
        label=ugettext_noop("URL"),
    )
    message_param = TrimmedCharField(
        label=ugettext_noop("Message Parameter"),
    )
    number_param = TrimmedCharField(
        label=ugettext_noop("Phone Number Parameter"),
    )
    include_plus = BooleanField(
        required=False,
        label=ugettext_noop("Include '+' in Phone Number"),
    )
    method = ChoiceField(
        label=ugettext_noop("HTTP Request Method"),
        choices=(
            ("GET", "GET"),
            ("POST", "POST")
        ),
    )
    additional_params = RecordListField(
        input_name="additional_params",
        label=ugettext_noop("Additional Parameters"),
    )

    def __init__(self, *args, **kwargs):
        if "initial" in kwargs and "additional_params" in kwargs["initial"]:
            additional_params_dict = kwargs["initial"]["additional_params"]
            kwargs["initial"]["additional_params"] = [
                {"name": key, "value": value}
                for key, value in additional_params_dict.items()
            ]
        super(HttpBackendForm, self).__init__(*args, **kwargs)

    def clean_url(self):
        value = self.cleaned_data.get("url")
        return form_clean_url(value)

    def clean_additional_params(self):
        value = self.cleaned_data.get("additional_params")
        result = {}
        for pair in value:
            name = pair["name"].strip()
            value = pair["value"].strip()
            if name == "" or value == "":
                raise ValidationError("Please enter both name and value.")
            if name in result:
                raise ValidationError("Parameter name entered twice: %s" % name)
            result[name] = value
        return result

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("HTTP Settings"),
            'url',
            'method',
            'message_param',
            'number_param',
            'include_plus',
            'additional_params',
        )
