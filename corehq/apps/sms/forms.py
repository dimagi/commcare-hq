import re
import json
from datetime import time
from crispy_forms.bootstrap import StrictButton, InlineField, FormActions
from crispy_forms.helper import FormHelper
from django import forms
from django.forms.forms import Form
from django.forms.fields import *
from crispy_forms import layout as crispy
from django.utils.safestring import mark_safe
from corehq.apps.hqwebapp.crispy import (BootstrapMultiField, ErrorsOnlyField,
    FieldWithHelpBubble, HiddenFieldWithErrors)
from corehq.apps.sms.models import FORWARD_ALL, FORWARD_BY_KEYWORD
from django.core.exceptions import ValidationError
from corehq.apps.sms.mixin import SMSBackend
from corehq.apps.reminders.forms import RecordListField, validate_time
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.sms.util import get_available_backends, validate_phone_number
from corehq.apps.domain.models import DayTimeWindow
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from dimagi.utils.django.fields import TrimmedCharField
from django.conf import settings

FORWARDING_CHOICES = (
    (FORWARD_ALL, ugettext_noop("All messages")),
    (FORWARD_BY_KEYWORD, ugettext_noop("All messages starting with a keyword")),
)

ENABLED = "ENABLED"
DISABLED = "DISABLED"

ENABLED_DISABLED_CHOICES = (
    (DISABLED, ugettext_noop("Disabled")),
    (ENABLED, ugettext_noop("Enabled")),
)

DEFAULT = "DEFAULT"
CUSTOM = "CUSTOM"

DEFAULT_CUSTOM_CHOICES = (
    (DEFAULT, ugettext_noop("Default")),
    (CUSTOM, ugettext_noop("Specify:")),
)

SMS_CONVERSATION_LENGTH_CHOICES = (
    (5, 5),
    (10, 10),
    (15, 15),
    (20, 20),
    (25, 25),
    (30, 30),
)

SHOW_ALL = "SHOW_ALL"
SHOW_INVALID = "SHOW_INVALID"
HIDE_ALL = "HIDE_ALL"

TIME_BEFORE = "BEFORE"
TIME_AFTER = "AFTER"
TIME_BETWEEN = "BETWEEN"

class SMSSettingsForm(Form):
    _cchq_is_previewer = False
    use_default_sms_response = BooleanField(required=False)
    default_sms_response = TrimmedCharField(required=False)
    send_to_duplicated_case_numbers = BooleanField(required=False)
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
    filter_surveys_from_chat = BooleanField(required=False)
    show_invalid_survey_responses_in_chat = BooleanField(required=False)
    count_messages_as_read_by_anyone = BooleanField(required=False)

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
                if start_time >= end_time:
                    raise ValidationError(_("End time must come after start time."))
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

    def clean_show_invalid_survey_responses_in_chat(self):
        value = self.cleaned_data.get("show_invalid_survey_responses_in_chat", False)
        if self.cleaned_data.get("filter_surveys_from_chat", False):
            return value
        else:
            return False

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


class LoadBalancingBackendFormMixin(Form):
    phone_numbers = CharField(required=False)

    def clean_phone_numbers(self):
        """
        Expects a list of [{"phone_number": <phone number>}] as the value.
        """
        value = self.cleaned_data.get("phone_numbers")
        result = []
        try:
            value = json.loads(value)
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, dict)
                assert "phone_number" in item
                result.append(item["phone_number"])
        except (AssertionError, ValueError):
            raise ValidationError(_("Something went wrong. Please reload the "
                "page and try again."))

        if len(result) == 0:
            raise ValidationError(_("You must specify at least one phone"
                "number."))

        for phone_number in result:
            validate_phone_number(phone_number)

        return result


class SettingsForm(Form):
    # General Settings
    use_default_sms_response = ChoiceField(
        required=False,
        label=ugettext_noop("Default SMS Response"),
        choices=ENABLED_DISABLED_CHOICES,
    )
    default_sms_response = TrimmedCharField(
        required=False,
        label="",
    )
    use_restricted_sms_times = ChoiceField(
        required=False,
        label=ugettext_noop("Send SMS on..."),
        choices=(
            (DISABLED, ugettext_noop("any day, at any time")),
            (ENABLED, ugettext_noop("only specific days and times")),
        ),
    )
    restricted_sms_times_json = CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    send_to_duplicated_case_numbers = ChoiceField(
        required=False,
        label=ugettext_noop("Send Messages to Non-Unique Phone Numbers"),
        choices=ENABLED_DISABLED_CHOICES,
    )

    # Chat Settings
    use_custom_case_username = ChoiceField(
        required=False,
        choices=DEFAULT_CUSTOM_CHOICES,
    )
    custom_case_username = TrimmedCharField(
        required=False,
        label=ugettext_noop("Enter a Case Property"),
    )
    use_custom_message_count_threshold = ChoiceField(
        required=False,
        choices=DEFAULT_CUSTOM_CHOICES,
    )
    custom_message_count_threshold = IntegerField(
        required=False,
        label=ugettext_noop("Enter a Number"),
    )
    use_sms_conversation_times = ChoiceField(
        required=False,
        label=ugettext_noop("Delay Automated SMS"),
        choices=ENABLED_DISABLED_CHOICES,
    )
    sms_conversation_times_json = CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    sms_conversation_length = ChoiceField(
        required=False,
        label=ugettext_noop("Conversation Duration"),
        choices=SMS_CONVERSATION_LENGTH_CHOICES,
    )
    survey_traffic_option = ChoiceField(
        required=False,
        label=ugettext_noop("Survey Traffic"),
        choices=(
            (SHOW_ALL, ugettext_noop("Show all survey traffic")),
            (SHOW_INVALID, ugettext_noop("Hide all survey traffic except "
                                         "invalid responses")),
            (HIDE_ALL, ugettext_noop("Hide all survey traffic")),
        ),
    )
    count_messages_as_read_by_anyone = ChoiceField(
        required=False,
        label=ugettext_noop("A Message is Read..."),
        choices=(
            (ENABLED, ugettext_noop("when it is read by anyone")),
            (DISABLED, ugettext_noop("only for the user that reads it")),
        ),
    )
    use_custom_chat_template = ChoiceField(
        required=False,
        choices=DEFAULT_CUSTOM_CHOICES,
    )
    custom_chat_template = TrimmedCharField(
        required=False,
        label=ugettext_noop("Enter Chat Template Identifier"),
    )
    sms_case_registration_enabled = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=ugettext_noop("Case Self-Registration"),
    )
    sms_case_registration_type = TrimmedCharField(
        required=False,
        label=ugettext_noop("Default Case Type"),
    )
    sms_case_registration_owner_id = ChoiceField(
        required=False,
        label=ugettext_noop("Default Case Owner"),
    )
    sms_case_registration_user_id = ChoiceField(
        required=False,
        label=ugettext_noop("Registration Submitter"),
    )

    @property
    def section_general(self):
        fields = [
            BootstrapMultiField(
                _("Default SMS Response"),
                InlineField(
                    "use_default_sms_response",
                    data_bind="value: use_default_sms_response",
                ),
                InlineField(
                    "default_sms_response",
                    css_class="input-xxlarge",
                    placeholder=_("Enter Default Response"),
                    data_bind="visible: showDefaultSMSResponse",
                ),
                help_bubble_text=_("Enable this option to provide a "
                    "default response when a user's incoming SMS does not "
                    "answer an open survey or match a known keyword."),
                css_id="default-sms-response-group",
            ),
            FieldWithHelpBubble(
                "use_restricted_sms_times",
                data_bind="value: use_restricted_sms_times",
                help_bubble_text=_("Use this option to limit the times "
                    "that SMS messages can be sent to users. Messages that "
                    "are sent outside these windows will remained queued "
                    "and will go out as soon as another window opens up."),
            ),
            BootstrapMultiField(
                "",
                HiddenFieldWithErrors("restricted_sms_times_json",
                    data_bind="value: restricted_sms_times_json"),
                crispy.Div(
                    data_bind="template: {"
                              " name: 'ko-template-restricted-sms-times', "
                              " data: $data"
                              "}",
                ),
                data_bind="visible: showRestrictedSMSTimes",
            ),
            FieldWithHelpBubble(
                "send_to_duplicated_case_numbers",
                help_bubble_text=_("Enabling this option will send "
                    "outgoing-only messages to phone numbers registered "
                    "with more than one mobile worker or case. SMS surveys "
                    "and keywords will still only work for unique phone "
                    "numbers in your project."),
            ),
        ]
        return crispy.Fieldset(
            _("General Settings"),
            *fields
        )

    @property
    def section_registration(self):
        fields = [
            FieldWithHelpBubble(
                "sms_case_registration_enabled",
                help_bubble_text=_("When this option is enabled, a person "
                    "can send an SMS into the system saying 'join "
                    "[project]', where [project] is your project "
                    "space name, and the system will automatically "
                    "create a case tied to that person's phone number."),
                data_bind="value: sms_case_registration_enabled",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    "sms_case_registration_type",
                    placeholder=_("Enter a Case Type"),
                    help_bubble_text=_("Cases that self-register over SMS "
                        "will be given this case type."),
                ),
                FieldWithHelpBubble(
                    "sms_case_registration_owner_id",
                    help_bubble_text=_("Cases that self-register over SMS "
                        "will be owned by this user or user group."),
                ),
                FieldWithHelpBubble(
                    "sms_case_registration_user_id",
                    help_bubble_text=_("The form submission for a "
                        "self-registration will belong to this user."),
                ),
                data_bind="visible: showRegistrationOptions",
            ),
        ]
        return crispy.Fieldset(
            _("Registration Settings"),
            *fields
        )

    @property
    def section_chat(self):
        fields = [
            BootstrapMultiField(
                _("Case Name Display"),
                InlineField(
                    "use_custom_case_username",
                    data_bind="value: use_custom_case_username",
                ),
                InlineField(
                    "custom_case_username",
                    css_class="input-large",
                    data_bind="visible: showCustomCaseUsername",
                ),
                help_bubble_text=_("By default, when chatting with a case, "
                    "the chat window will use the case's \"name\" case "
                    "property when displaying the case's name. To use a "
                    "different case property, specify it here."),
                css_id="custom-case-username-group",
            ),
            BootstrapMultiField(
                _("Counter Threshold"),
                InlineField(
                    "use_custom_message_count_threshold",
                    data_bind="value: use_custom_message_count_threshold",
                ),
                InlineField(
                    "custom_message_count_threshold",
                    css_class="input-large",
                    data_bind="visible: showCustomMessageCountThreshold",
                ),
                help_bubble_text=_("The chat window keeps track of how many "
                    "messages are being sent and received, and will "
                    "highlight the counter after it reaches 50. To use a "
                    "different threshold than 50, enter it here."),
                css_id="custom-message-count-threshold-group",
            ),
            FieldWithHelpBubble(
                "use_sms_conversation_times",
                data_bind="value: use_sms_conversation_times",
                help_bubble_text=_("When this option is enabled, the system "
                    "will not send automated SMS to chat recipients when "
                    "those recipients are in the middle of a conversation."),
            ),
            BootstrapMultiField(
                "",
                HiddenFieldWithErrors("sms_conversation_times_json",
                    data_bind="value: sms_conversation_times_json"),
                crispy.Div(
                    data_bind="template: {"
                              " name: 'ko-template-sms-conversation-times', "
                              " data: $data"
                              "}",
                ),
                data_bind="visible: showSMSConversationTimes",
            ),
            crispy.Div(
                FieldWithHelpBubble(
                    "sms_conversation_length",
                    help_bubble_text=_("The number of minutes to wait "
                        "after receiving an incoming SMS from a chat "
                        "recipient before resuming automated SMS to that "
                        "recipient."),
                ),
                data_bind="visible: showSMSConversationTimes",
            ),
            FieldWithHelpBubble(
                "survey_traffic_option",
                help_bubble_text=_("This option allows you to hide a chat "
                    "recipient's survey questions and responses from chat "
                    "windows. There is also the option to show only invalid "
                    "responses to questions in the chat window, which could "
                    "be attempts to converse."),
            ),
            FieldWithHelpBubble(
                "count_messages_as_read_by_anyone",
                help_bubble_text=_("The chat window will mark unread "
                    "messages to the user viewing them. Use this option to "
                    "control whether a message counts as being read if it "
                    "is read by anyone, or if it counts as being read only "
                    "to the user who reads it."),
            ),
        ]
        if self._cchq_is_previewer:
            fields.append(
                BootstrapMultiField(
                    _("Chat Template"),
                    InlineField(
                        "use_custom_chat_template",
                        data_bind="value: use_custom_chat_template",
                    ),
                    InlineField(
                        "custom_chat_template",
                        data_bind="visible: showCustomChatTemplate",
                    ),
                    help_bubble_text=_("To use a custom template to render the "
                        "chat window, enter it here."),
                    css_id="custom-chat-template-group",
                )
            )
        return crispy.Fieldset(
            _("Chat Settings"),
            *fields
        )

    def __init__(self, data=None, cchq_domain=None, cchq_is_previewer=False,
        *args, **kwargs):
        self._cchq_domain = cchq_domain
        self._cchq_is_previewer = cchq_is_previewer
        super(SettingsForm, self).__init__(data, *args, **kwargs)
        self.populate_dynamic_choices()

        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.layout = crispy.Layout(
            self.section_general,
            self.section_registration,
            self.section_chat,
            FormActions(
                StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn-primary",
                ),
            ),
        )
        self.restricted_sms_times_widget_context = {
            "template_name": "ko-template-restricted-sms-times",
            "explanation_text": _("SMS will only be sent when any of the following is true:"),
            "ko_array_name": "restricted_sms_times",
            "remove_window_method": "$parent.removeRestrictedSMSTime",
            "add_window_method": "addRestrictedSMSTime",
        }
        self.sms_conversation_times_widget_context = {
            "template_name": "ko-template-sms-conversation-times",
            "explanation_text": _("Automated SMS will be suppressed during "
                                  "chat conversations when any of the following "
                                  "is true:"),
            "ko_array_name": "sms_conversation_times",
            "remove_window_method": "$parent.removeSMSConversationTime",
            "add_window_method": "addSMSConversationTime",
        }

    @property
    def current_values(self):
        current_values = {}
        for field_name in self.fields.keys():
            value = self[field_name].value()
            if field_name in ["restricted_sms_times_json",
                "sms_conversation_times_json"]:
                if isinstance(value, basestring):
                    current_values[field_name] = json.loads(value)
                else:
                    current_values[field_name] = value
            else:
                current_values[field_name] = value
        return current_values

    def populate_dynamic_choices(self):
        groups = Group.get_case_sharing_groups(self._cchq_domain)
        users = CommCareUser.by_domain(self._cchq_domain)

        domain_group_choices = [(group._id, group.name) for group in groups]
        domain_user_choices = [(user._id, user.raw_username) for user in users]
        domain_owner_choices = domain_group_choices + domain_user_choices

        choose = [("", _("(Choose)"))]
        self.fields["sms_case_registration_owner_id"].choices = (
            choose + domain_owner_choices)
        self.fields["sms_case_registration_user_id"].choices = (
            choose + domain_user_choices)

    def _clean_dependent_field(self, bool_field, field):
        if self.cleaned_data.get(bool_field):
            value = self.cleaned_data.get(field, None)
            if not value:
                raise ValidationError(_("This field is required."))
            return value
        else:
            return None

    def clean_use_default_sms_response(self):
        return self.cleaned_data.get("use_default_sms_response") == ENABLED

    def clean_default_sms_response(self):
        return self._clean_dependent_field("use_default_sms_response",
            "default_sms_response")

    def clean_use_custom_case_username(self):
        return self.cleaned_data.get("use_custom_case_username") == CUSTOM

    def clean_custom_case_username(self):
        return self._clean_dependent_field("use_custom_case_username",
            "custom_case_username")

    def clean_use_custom_message_count_threshold(self):
        return (self.cleaned_data.get("use_custom_message_count_threshold")
            == CUSTOM)

    def clean_custom_message_count_threshold(self):
        value = self._clean_dependent_field("use_custom_message_count_threshold",
            "custom_message_count_threshold")
        if value is not None and value <= 0:
            raise ValidationError(_("Please enter a positive number"))
        return value

    def clean_use_custom_chat_template(self):
        if not self._cchq_is_previewer:
            return None
        return self.cleaned_data.get("use_custom_chat_template") == CUSTOM

    def clean_custom_chat_template(self):
        if not self._cchq_is_previewer:
            return None
        value = self._clean_dependent_field("use_custom_chat_template",
            "custom_chat_template")
        if value is not None and value not in settings.CUSTOM_CHAT_TEMPLATES:
            raise ValidationError(_("Unknown custom template identifier."))
        return value

    def _clean_time_window_json(self, field_name):
        try:
            time_window_json = json.loads(self.cleaned_data.get(field_name))
        except ValueError:
            raise ValidationError(_("An error has occurred. Please try again, "
                "and if the problem persists, please report an issue."))
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
                    end_time=end_time,
                ))
            elif time_input_relationship == TIME_AFTER:
                start_time = validate_time(start_time)
                result.append(DayTimeWindow(
                    day=day,
                    start_time=start_time,
                    end_time=None,
                ))
            else:
                start_time = validate_time(start_time)
                end_time = validate_time(end_time)
                if start_time >= end_time:
                    raise ValidationError(_("End time must come after start "
                        "time."))
                result.append(DayTimeWindow(
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                ))
        return result

    def clean_use_restricted_sms_times(self):
        return self.cleaned_data.get("use_restricted_sms_times") == ENABLED

    def clean_restricted_sms_times_json(self):
        if self.cleaned_data.get("use_restricted_sms_times"):
            return self._clean_time_window_json("restricted_sms_times_json")
        else:
            return []

    def clean_use_sms_conversation_times(self):
        return self.cleaned_data.get("use_sms_conversation_times") == ENABLED

    def clean_sms_conversation_times_json(self):
        if self.cleaned_data.get("use_sms_conversation_times"):
            return self._clean_time_window_json("sms_conversation_times_json")
        else:
            return []

    def clean_send_to_duplicated_case_numbers(self):
        return (self.cleaned_data.get("send_to_duplicated_case_numbers")
            == ENABLED)

    def clean_count_messages_as_read_by_anyone(self):
        return (self.cleaned_data.get("count_messages_as_read_by_anyone")
            == ENABLED)

    def clean_sms_case_registration_enabled(self):
        return (self.cleaned_data.get("sms_case_registration_enabled")
            == ENABLED)

    def _clean_registration_id_field(self, field_name):
        if self.cleaned_data.get("sms_case_registration_enabled"):
            value = self.cleaned_data.get(field_name)
            if not value:
                raise ValidationError(_("This field is required."))
            # Otherwise, the ChoiceField automatically validates that it is
            # in the list that is dynamically populated in __init__
            return value
        else:
            return None

    def clean_sms_case_registration_owner_id(self):
        return self._clean_registration_id_field("sms_case_registration_owner_id")

    def clean_sms_case_registration_user_id(self):
        return self._clean_registration_id_field("sms_case_registration_user_id")

    def clean_sms_conversation_length(self):
        # Just cast to int, the ChoiceField will validate that it is an integer
        return int(self.cleaned_data.get("sms_conversation_length"))

class BackendForm(Form):
    _cchq_domain = None
    _cchq_backend_id = None
    name = CharField(
        label=ugettext_noop("Name")
    )
    description = CharField(
        label=ugettext_noop("Description"),
        widget=forms.Textarea,
        required=False,
    )
    give_other_domains_access = BooleanField(
        required=False,
        label=ugettext_noop("Give other domains access.")
    )
    authorized_domains = CharField(
        required=False,
        label=ugettext_noop("List of authorized domains")
    )
    reply_to_phone_number = CharField(
        required=False,
        label=ugettext_noop("Reply-To Phone Number"),
    )

    def __init__(self, *args, **kwargs):
        button_text = kwargs.pop('button_text', _("Create SMS Connection"))
        super(BackendForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form form-horizontal'
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
               _('General Settings'),
                crispy.Field('name', css_class='input-xxlarge'),
                crispy.Field('description', css_class='input-xxlarge', rows="3"),
                crispy.Field('reply_to_phone_number', css_class='input-xxlarge'),
                crispy.Field(
                    'give_other_domains_access',
                    data_bind="checked: share_backend"
                ),
                crispy.Div(
                    'authorized_domains',
                    data_bind="visible: showAuthorizedDomains",
                ),
            ),
            self.gateway_specific_fields,
            crispy.Fieldset(
                _("Phone Numbers"),
                crispy.Div(
                    data_bind="template: {"
                              " name: 'ko-load-balancing-template', "
                              " data: $data"
                              "}",
                ),
                data_bind="visible: use_load_balancing",
            ),
            FormActions(
                StrictButton(
                    button_text,
                    type="submit",
                    css_class='btn-primary'
                ),
            ),
        )

    @property
    def gateway_specific_fields(self):
        return crispy.Div()

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
    stock_out_facilities = BooleanField(
        label=ugettext_lazy("Receive stockout facilities SMS alert"),
        required=False,
        help_text=ugettext_lazy("This will alert you with specific users/facilities that are stocked out of your commodities")
    )
    stock_out_commodities = BooleanField(
        label=ugettext_lazy("Receive stockout commodities SMS alert"),
        required=False,
        help_text=ugettext_lazy("This will alert you with specific commodities that are stocked out by your users/facilities")
    )
    stock_out_rates = BooleanField(
        label=ugettext_lazy("Receive stockout SMS alert"),
        required=False,
        help_text=ugettext_lazy("This will alert you with the percent of facilities that are stocked out of a specific commodity")
    )
    non_report = BooleanField(
        label=ugettext_lazy("Receive non-reporting SMS alert"),
        required=False,
        help_text=ugettext_lazy("This alert highlight users/facilities which have not submitted their CommTrack stock report.")
    )

    def save(self, commtrack_settings):
        alert_config = commtrack_settings.alert_config
        alert_config.stock_out_facilities = self.cleaned_data.get("stock_out_facilities", False)
        alert_config.stock_out_commodities = self.cleaned_data.get("stock_out_commodities", False)
        alert_config.stock_out_rates = self.cleaned_data.get("stock_out_rates", False)
        alert_config.non_report = self.cleaned_data.get("non_report", False)

        commtrack_settings.save()
