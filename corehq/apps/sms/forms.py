import re
from crispy_forms.bootstrap import StrictButton, InlineField
from crispy_forms.helper import FormHelper
from django import forms
from django.forms.forms import Form
from django.forms.fields import *
from crispy_forms import layout as crispy
from django.utils.safestring import mark_safe
from corehq.apps.hqwebapp.crispy import BootstrapMultiField
from corehq.apps.sms.models import FORWARD_ALL, FORWARD_BY_KEYWORD
from django.core.exceptions import ValidationError
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.reminders.forms import RecordListField
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.sms.util import get_available_backends
from dimagi.utils.django.fields import TrimmedCharField
from django.conf import settings

FORWARDING_CHOICES = (
    (FORWARD_ALL, ugettext_noop("All messages")),
    (FORWARD_BY_KEYWORD, ugettext_noop("All messages starting with a keyword")),
)

class SMSSettingsForm(Form):
    _cchq_is_previewer = False
    use_default_sms_response = BooleanField(required=False)
    default_sms_response = TrimmedCharField(required=False)
    use_custom_case_username = BooleanField(required=False)
    custom_case_username = TrimmedCharField(required=False)
    use_custom_message_count_threshold = BooleanField(required=False)
    custom_message_count_threshold = IntegerField(required=False)
    use_custom_chat_template = BooleanField(required=False)
    custom_chat_template = TrimmedCharField(required=False)

    def _clean_dependent_field(self, bool_field, field):
        if self.cleaned_data.get(bool_field):
            value = self.cleaned_data.get(field, None)
            if not value:
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_default_sms_response(self):
        return self._clean_dependent_field("use_default_sms_response", "default_sms_response")

    def clean_custom_case_username(self):
        if not self._cchq_is_previewer:
            return None
        return self._clean_dependent_field("use_custom_case_username", "custom_case_username")

    def clean_custom_message_count_threshold(self):
        if not self._cchq_is_previewer:
            return None
        value = self._clean_dependent_field("use_custom_message_count_threshold", "custom_message_count_threshold")
        if value is not None and value < 0:
            raise ValidationError(_("Please enter a positive number"))
        return value

    def clean_custom_chat_template(self):
        if not self._cchq_is_previewer:
            return None
        value = self._clean_dependent_field("use_custom_chat_template", "custom_chat_template")
        if value is not None and value not in settings.CUSTOM_CHAT_TEMPLATES:
            raise ValidationError(_("Unknown custom template identifier."))
        return value

class ForwardingRuleForm(Form):
    forward_type = ChoiceField(choices=FORWARDING_CHOICES)
    keyword = CharField(required=False)
    backend_id = CharField()
    
    def clean_keyword(self):
        forward_type = self.cleaned_data.get("forward_type")
        keyword = self.cleaned_data.get("keyword", "").strip()
        if forward_type == FORWARD_BY_KEYWORD:
            if keyword == "":
                raise ValidationError(_("This field is required."))
            return keyword
        else:
            return None

class BackendForm(Form):
    _cchq_domain = None
    _cchq_backend_id = None
    name = CharField()
    give_other_domains_access = BooleanField(required=False)
    authorized_domains = CharField(required=False)
    reply_to_phone_number = CharField(required=False)

    def clean_name(self):
        value = self.cleaned_data.get("name")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError(_("This field is required."))
        if re.compile("\s").search(value) is not None:
            raise ValidationError(_("Name may not contain any spaces."))

        backend_classes = get_available_backends()
        if self._cchq_domain is None:
            # Ensure name is not duplicated among other global backends
            backend = SMSBackend.view(
                "sms/global_backends",
                classes=backend_classes,
                key=[value],
                include_docs=True,
                reduce=False
            ).one()
        else:
            # Ensure name is not duplicated among other backends owned by this domain
            backend = SMSBackend.view("sms/backend_by_owner_domain", classes=backend_classes, key=[self._cchq_domain, value], include_docs=True).one()
        if backend is not None and backend._id != self._cchq_backend_id:
            raise ValidationError(_("Name is already in use."))
        
        return value

    def clean_authorized_domains(self):
        if not self.cleaned_data.get("give_other_domains_access"):
            return []
        else:
            value = self.cleaned_data.get("authorized_domains")
            if value is None or value.strip() == "":
                return []
            else:
                return [domain.strip() for domain in value.split(",")]

    def clean_reply_to_phone_number(self):
        value = self.cleaned_data.get("reply_to_phone_number")
        if value is None:
            return None
        else:
            value = value.strip()
            if value == "":
                return None
            else:
                return value

class BackendMapForm(Form):
    catchall_backend_id = CharField(required=False)
    backend_map = RecordListField(input_name="backend_map")

    def clean_backend_map(self):
        cleaned_value = {}
        for record in self.cleaned_data.get("backend_map", []):
            prefix = record["prefix"].strip()
            try:
                prefix = int(prefix)
                assert prefix > 0
            except (ValueError, AssertionError):
                raise ValidationError(_("Please enter a positive number for the prefix."))
            prefix = str(prefix)
            if prefix in cleaned_value:
                raise ValidationError(_("Prefix is specified twice:") + prefix)
            cleaned_value[prefix] = record["backend_id"]
        return cleaned_value

    def clean_catchall_backend_id(self):
        value = self.cleaned_data.get("catchall_backend_id", None)
        if value == "":
            return None
        else:
            return value


class InitiateAddSMSBackendForm(Form):
    action = CharField(
        initial='new_backend',
        widget=forms.HiddenInput(),
    )
    backend_type = ChoiceField(
        required=False,
        label="Connection Type",
    )

    def __init__(self, is_superuser=False, *args, **kwargs):
        super(InitiateAddSMSBackendForm, self).__init__(*args, **kwargs)
        backend_classes = get_available_backends()
        backend_choices = []
        for name, klass in backend_classes.items():
            if is_superuser or name == "TelerivetBackend":
                try:
                    friendly_name = klass.get_generic_name()
                except NotImplementedError:
                    friendly_name = name
                backend_choices.append((name, friendly_name))
        self.fields['backend_type'].choices = backend_choices

        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.layout = crispy.Layout(
            BootstrapMultiField(
                _("Create Another Connection"),
                InlineField('action'),
                InlineField('backend_type'),
                StrictButton(
                    mark_safe('<i class="icon-plus"></i> %s' % "Add Another Gateway"),
                    css_class='btn-success',
                    type='submit',
                    style="margin-left:5px;"
                ),
            ),
        )

class SubscribeSMSForm(Form):
    stock_out_facilities = BooleanField(label=_("Receive stockout facilities SMS alert"), required=False, help_text=_("This will alert you with specific users/facilities that are stocked out of your commodities"))
    stock_out_commodities = BooleanField(label=_("Receive stockout commodities SMS alert"), required=False, help_text=_("This will alert you with specific commodities that are stocked out by your users/facilities"))
    stock_out_rates = BooleanField(label=_("Receive stockout SMS alert"), required=False, help_text=_("This will alert you with the percent of facilities that are stocked out of a specific commodity"))
    non_report = BooleanField(label=_("Receive non-reporting SMS alert"), required=False, help_text=_("This alert highlight users/facilities which have not submitted their CommTrack stock report."))

    def save(self, commtrack_settings):
        alert_config = commtrack_settings.alert_config
        alert_config.stock_out_facilities = self.cleaned_data.get("stock_out_facilities", False)
        alert_config.stock_out_commodities = self.cleaned_data.get("stock_out_commodities", False)
        alert_config.stock_out_rates = self.cleaned_data.get("stock_out_rates", False)
        alert_config.non_report = self.cleaned_data.get("non_report", False)

        commtrack_settings.save()
