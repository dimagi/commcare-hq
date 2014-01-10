import re
import json
from datetime import time
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
from corehq.apps.reminders.forms import RecordListField, validate_time
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.sms.util import get_available_backends
from corehq.apps.domain.models import DayTimeWindow
from dimagi.utils.django.fields import TrimmedCharField
from django.conf import settings

FORWARDING_CHOICES = (
    (FORWARD_ALL, ugettext_noop("All messages")),
    (FORWARD_BY_KEYWORD, ugettext_noop("All messages starting with a keyword")),
)

SMS_CONVERSATION_LENGTH_CHOICES = (
    (5, 5),
    (10, 10),
    (15, 15),
    (20, 20),
    (25, 25),
    (30, 30),
)

TIME_BEFORE = "BEFORE"
TIME_AFTER = "AFTER"
TIME_BETWEEN = "BETWEEN"

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
    use_restricted_sms_times = BooleanField(required=False)
    restricted_sms_times_json = CharField(required=False)
    use_sms_conversation_times = BooleanField(required=False)
    sms_conversation_times_json = CharField(required=False)
    sms_conversation_length = ChoiceField(
        choices=SMS_CONVERSATION_LENGTH_CHOICES,
        required=False,
    )

    def initialize_time_window_fields(self, initial, bool_field, json_field):
        time_window_json = [w.to_json() for w in initial]
        self.initial[json_field] = json.dumps(time_window_json)
        if len(initial) > 0:
            self.initial[bool_field] = True
        else:
            self.initial[bool_field] = False

    def __init__(self, *args, **kwargs):
        self._cchq_is_previewer = kwargs.pop("_cchq_is_previewer", False)
        super(SMSSettingsForm, self).__init__(*args, **kwargs)
        if "initial" in kwargs:
            self.initialize_time_window_fields(
                kwargs["initial"].get("restricted_sms_times", []),
                "use_restricted_sms_times",
                "restricted_sms_times_json"
            )
            self.initialize_time_window_fields(
                kwargs["initial"].get("sms_conversation_times", []),
                "use_sms_conversation_times",
                "sms_conversation_times_json"
            )
        if settings.SMS_QUEUE_ENABLED and self._cchq_is_previewer:
            self.fields["sms_conversation_length"].required = True

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

    def _clean_time_window_json(self, field_name):
        try:
            time_window_json = json.loads(self.cleaned_data.get(field_name))
        except ValueError:
            raise ValidationError(_("An error has occurred. Please try again, and if the problem persists, please report an issue."))
        result = []
        for window in time_window_json:
            day = window.get("day")
            start_time = window.get("start_time")
            end_time = window.get("end_time")
            time_input_relationship = window.get("time_input_relationship")

            try:
                day = int(day)
                assert day >= -1 and day <= 6
            except (ValueError, AssertionError):
                raise ValidationError(_("Invalid day chosen."))

            if time_input_relationship == TIME_BEFORE:
                end_time = validate_time(end_time)
                result.append(DayTimeWindow(
                    day=day,
                    start_time=None,
                    end_time=end_time
                ))
            elif time_input_relationship == TIME_AFTER:
                start_time = validate_time(start_time)
                result.append(DayTimeWindow(
                    day=day,
                    start_time=start_time,
                    end_time=None
                ))
            else:
                start_time = validate_time(start_time)
                end_time = validate_time(end_time)
                result.append(DayTimeWindow(
                    day=day,
                    start_time=start_time,
                    end_time=end_time
                ))
        return result

    def clean_restricted_sms_times_json(self):
        if self.cleaned_data.get("use_restricted_sms_times", False):
            return self._clean_time_window_json("restricted_sms_times_json")
        else:
            return []

    def clean_sms_conversation_times_json(self):
        if self.cleaned_data.get("use_sms_conversation_times", False):
            return self._clean_time_window_json("sms_conversation_times_json")
        else:
            return []

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
