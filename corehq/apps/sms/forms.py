from __future__ import absolute_import
from __future__ import unicode_literals
import re
import json
from couchdbkit.exceptions import ResourceNotFound
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.layout import Div
from django import forms
from django.urls import reverse
from django.forms.forms import Form
from django.forms.fields import *
from crispy_forms import layout as crispy
from crispy_forms import bootstrap as twbscrispy
from django.utils.safestring import mark_safe
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.hqwebapp.widgets import SelectToggle
from corehq.apps.app_manager.dbaccessors import get_built_app_ids
from corehq.apps.app_manager.models import Application
from corehq.apps.sms.models import FORWARD_ALL, FORWARD_BY_KEYWORD, SQLMobileBackend
from django.core.exceptions import ValidationError
from corehq.apps.reminders.forms import validate_time
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.sms.util import (validate_phone_number, strip_plus,
    get_sms_backend_classes, ALLOWED_SURVEY_DATE_FORMATS)
from corehq.apps.domain.models import DayTimeWindow
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.util.python_compatibility import soft_assert_type_text
from dimagi.utils.django.fields import TrimmedCharField
from dimagi.utils.couch.database import iter_docs
from django.conf import settings
import six

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
    (CUSTOM, ugettext_noop("Custom")),
)

MESSAGE_COUNTER_CHOICES = (
    (DEFAULT, ugettext_noop("Don't use counter")),
    (CUSTOM, ugettext_noop("Use counter with threshold:")),
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

WELCOME_RECIPIENT_NONE = 'NONE'
WELCOME_RECIPIENT_CASE = 'CASE'
WELCOME_RECIPIENT_MOBILE_WORKER = 'MOBILE_WORKER'
WELCOME_RECIPIENT_ALL = 'ALL'

WELCOME_RECIPIENT_CHOICES = (
    (WELCOME_RECIPIENT_NONE, ugettext_lazy('Nobody')),
    (WELCOME_RECIPIENT_CASE, ugettext_lazy('Cases only')),
    (WELCOME_RECIPIENT_MOBILE_WORKER, ugettext_lazy('Mobile Workers only')),
    (WELCOME_RECIPIENT_ALL, ugettext_lazy('Cases and Mobile Workers')),
)


class ForwardingRuleForm(Form):
    forward_type = ChoiceField(choices=FORWARDING_CHOICES)
    keyword = CharField(required=False)
    backend_id = CharField()

    def __init__(self, *args, **kwargs):
        super(ForwardingRuleForm, self).__init__(*args, **kwargs)

        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Forwarding Rule Options'),
                'forward_type',
                crispy.Div(
                    'keyword',
                    css_id="keyword_row",
                    css_class='hide',
                ),
                'backend_id',
                hqcrispy.FormActions(
                    twbscrispy.StrictButton(
                        _("Submit"),
                        type="submit",
                        css_class="btn btn-primary",
                    ),
                ),
            )
        )

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

    sms_survey_date_format = ChoiceField(
        required=False,
        label=ugettext_lazy("SMS Survey Date Format"),
        choices=(
            (df.human_readable_format, ugettext_lazy(df.human_readable_format))
            for df in ALLOWED_SURVEY_DATE_FORMATS
        ),
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
        choices=MESSAGE_COUNTER_CHOICES,
    )
    custom_message_count_threshold = IntegerField(
        required=False,
        label=ugettext_noop("Enter a Number"),
    )
    use_sms_conversation_times = ChoiceField(
        required=False,
        label=ugettext_noop("Delay Automated SMS"),
        choices=ENABLED_DISABLED_CHOICES,
        widget=SelectToggle(choices=ENABLED_DISABLED_CHOICES, attrs={"ko_value": "use_sms_conversation_times"}),
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

    # Registration settings
    sms_case_registration_enabled = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=ugettext_noop("Case Self-Registration"),
    )
    sms_case_registration_type = TrimmedCharField(
        required=False,
        label=ugettext_noop("Default Case Type"),
    )
    sms_case_registration_owner_id = CharField(
        required=False,
        label=ugettext_noop("Default Case Owner"),
        widget=forms.Select(choices=[]),
    )
    sms_case_registration_user_id = CharField(
        required=False,
        label=ugettext_noop("Registration Submitter"),
        widget=forms.Select(choices=[]),
    )
    sms_mobile_worker_registration_enabled = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=ugettext_noop("SMS Mobile Worker Registration"),
    )
    registration_welcome_message = ChoiceField(
        choices=WELCOME_RECIPIENT_CHOICES,
        label=ugettext_lazy("Send registration welcome message to"),
    )

    # Internal settings
    override_daily_outbound_sms_limit = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=ugettext_lazy("Override Daily Outbound SMS Limit"),
    )
    custom_daily_outbound_sms_limit = IntegerField(
        required=False,
        label=ugettext_noop("Daily Outbound SMS Limit"),
        min_value=1000,
    )

    @property
    def section_general(self):
        fields = [
            hqcrispy.B3MultiField(
                _("Default SMS Response"),
                crispy.Div(
                    InlineField(
                        "use_default_sms_response",
                        data_bind="value: use_default_sms_response",
                    ),
                    css_class='col-sm-4'
                ),
                crispy.Div(
                    InlineField(
                        "default_sms_response",
                        css_class="input-xxlarge",
                        placeholder=_("Enter Default Response"),
                        data_bind="visible: showDefaultSMSResponse",
                    ),
                    css_class='col-sm-8'
                ),
                help_bubble_text=_("Enable this option to provide a "
                                   "default response when a user's incoming SMS does not "
                                   "answer an open survey or match a known keyword."),
                css_id="default-sms-response-group",
                field_class='col-sm-6 col-md-9 col-lg-9'
            ),
            hqcrispy.FieldWithHelpBubble(
                "use_restricted_sms_times",
                data_bind="value: use_restricted_sms_times",
                help_bubble_text=_("Use this option to limit the times "
                                   "that SMS messages can be sent to users. Messages that "
                                   "are sent outside these windows will remained queued "
                                   "and will go out as soon as another window opens up."),
            ),
            hqcrispy.B3MultiField(
                "",
                hqcrispy.HiddenFieldWithErrors("restricted_sms_times_json",
                                      data_bind="value: restricted_sms_times_json"),
                crispy.Div(
                    data_bind="template: {"
                              " name: 'ko-template-restricted-sms-times', "
                              " data: $data"
                              "}",
                ),
                data_bind="visible: showRestrictedSMSTimes",
            ),
            hqcrispy.FieldWithHelpBubble(
                'sms_survey_date_format',
                help_bubble_text=_("Choose the format in which date questions "
                                   "should be answered in SMS surveys."),
            ),
        ]
        return crispy.Fieldset(
            _("General Settings"),
            *fields
        )

    @property
    def section_registration(self):
        fields = [
            hqcrispy.FieldWithHelpBubble(
                "sms_case_registration_enabled",
                help_bubble_text=_("When this option is enabled, a person "
                    "can send an SMS into the system saying 'join "
                    "[project]', where [project] is your project "
                    "space name, and the system will automatically "
                    "create a case tied to that person's phone number."),
                data_bind="value: sms_case_registration_enabled",
            ),
            crispy.Div(
                hqcrispy.FieldWithHelpBubble(
                    "sms_case_registration_type",
                    placeholder=_("Enter a Case Type"),
                    help_bubble_text=_("Cases that self-register over SMS "
                        "will be given this case type."),
                ),
                hqcrispy.FieldWithHelpBubble(
                    "sms_case_registration_owner_id",
                    help_bubble_text=_("Cases that self-register over SMS "
                        "will be owned by this user or user group."),
                ),
                hqcrispy.FieldWithHelpBubble(
                    "sms_case_registration_user_id",
                    help_bubble_text=_("The form submission for a "
                        "self-registration will belong to this user."),
                ),
                data_bind="visible: showRegistrationOptions",
            ),
            hqcrispy.FieldWithHelpBubble(
                "sms_mobile_worker_registration_enabled",
                help_bubble_text=_("When this option is enabled, a person "
                    "can send an SMS into the system saying 'join "
                    "[project] worker [username]' (where [project] is your "
                    " project space and [username] is an optional username)"
                    ", and the system will add them as a mobile worker."),
            ),
            hqcrispy.FieldWithHelpBubble(
                'registration_welcome_message',
                help_bubble_text=_("Choose whether to send an automatic "
                    "welcome message to cases, mobile workers, or both, "
                    "after they self-register. The welcome message can be "
                    "configured in the SMS languages and translations page "
                    "(Messaging -> Languages -> Messaging Translations)."),
            ),
        ]
        return crispy.Fieldset(
            _("Registration Settings"),
            *fields
        )

    @property
    def section_chat(self):
        fields = [
            hqcrispy.B3MultiField(
                _("Case Name Display"),
                crispy.Div(
                    InlineField(
                        "use_custom_case_username",
                        data_bind="value: use_custom_case_username",
                    ),
                    css_class='col-sm-4'
                ),
                crispy.Div(
                    InlineField(
                        "custom_case_username",
                        css_class="input-large",
                        data_bind="visible: showCustomCaseUsername",
                    ),
                    css_class='col-sm-8'
                ),
                help_bubble_text=_("By default, when chatting with a case, "
                    "the chat window will use the case's \"name\" case "
                    "property when displaying the case's name. To use a "
                    "different case property, specify it here."),
                css_id="custom-case-username-group",
                field_class='col-sm-6 col-md-9 col-lg-9'
            ),
            hqcrispy.B3MultiField(
                _("Message Counter"),
                crispy.Div(
                    InlineField(
                        "use_custom_message_count_threshold",
                        data_bind="value: use_custom_message_count_threshold",
                    ),
                    css_class='col-sm-4'
                ),
                crispy.Div(
                    InlineField(
                        "custom_message_count_threshold",
                        css_class="input-large",
                        data_bind="visible: showCustomMessageCountThreshold",
                    ),
                    css_class='col-sm-8'
                ),


                help_bubble_text=_("The chat window can use a counter to keep "
                    "track of how many messages are being sent and received "
                    "and highlight that number after a certain threshold is "
                    "reached. By default, the counter is disabled. To enable "
                    "it, enter the desired threshold here."),
                css_id="custom-message-count-threshold-group",
                field_class='col-sm-6 col-md-9 col-lg-9'
            ),
            hqcrispy.FieldWithHelpBubble(
                "use_sms_conversation_times",
                help_bubble_text=_("When this option is enabled, the system "
                    "will not send automated SMS to chat recipients when "
                    "those recipients are in the middle of a conversation."),
            ),
            hqcrispy.B3MultiField(
                "",
                hqcrispy.HiddenFieldWithErrors("sms_conversation_times_json",
                    data_bind="value: sms_conversation_times_json"),
                crispy.Div(
                    data_bind="template: {"
                              " name: 'ko-template-sms-conversation-times', "
                              " data: $data"
                              "}",
                ),
                data_bind="visible: showSMSConversationTimes",
                label_class='hide',
                field_class='col-md-12 col-lg-10'
            ),
            crispy.Div(
                hqcrispy.FieldWithHelpBubble(
                    "sms_conversation_length",
                    help_bubble_text=_("The number of minutes to wait "
                        "after receiving an incoming SMS from a chat "
                        "recipient before resuming automated SMS to that "
                        "recipient."),
                ),
                data_bind="visible: showSMSConversationTimes",
            ),
            hqcrispy.FieldWithHelpBubble(
                "survey_traffic_option",
                help_bubble_text=_("This option allows you to hide a chat "
                    "recipient's survey questions and responses from chat "
                    "windows. There is also the option to show only invalid "
                    "responses to questions in the chat window, which could "
                    "be attempts to converse."),
            ),
            hqcrispy.FieldWithHelpBubble(
                "count_messages_as_read_by_anyone",
                help_bubble_text=_("The chat window will mark unread "
                    "messages to the user viewing them. Use this option to "
                    "control whether a message counts as being read if it "
                    "is read by anyone, or if it counts as being read only "
                    "to the user who reads it."),
            ),
        ]
        return crispy.Fieldset(
            _("Chat Settings"),
            *fields
        )

    @property
    def section_internal(self):
        return crispy.Fieldset(
            _("Internal Settings (Dimagi Only)"),
            hqcrispy.B3MultiField(
                _("Override Daily Outbound SMS Limit"),
                crispy.Div(
                    InlineField(
                        'override_daily_outbound_sms_limit',
                        data_bind='value: override_daily_outbound_sms_limit',
                    ),
                    css_class='col-sm-4'
                ),
                crispy.Div(
                    InlineField('custom_daily_outbound_sms_limit'),
                    data_bind="visible: override_daily_outbound_sms_limit() === '%s'" % ENABLED,
                    css_class='col-sm-8'
                ),
            ),
            hqcrispy.B3MultiField(
                _("Chat Template"),
                crispy.Div(
                    InlineField(
                        "use_custom_chat_template",
                        data_bind="value: use_custom_chat_template",
                    ),
                    css_class='col-sm-4'
                ),
                crispy.Div(
                    InlineField(
                        "custom_chat_template",
                        data_bind="visible: showCustomChatTemplate",
                    ),
                    css_class='col-sm-8'
                ),
                help_bubble_text=_("To use a custom template to render the "
                    "chat window, enter it here."),
                css_id="custom-chat-template-group",
            ),
        )

    @property
    def sections(self):
        result = [
            self.section_general,
            self.section_registration,
            self.section_chat,
        ]

        if self._cchq_is_previewer:
            result.append(self.section_internal)

        result.append(
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Save"),
                    type="submit",
                    css_class="btn-primary",
                ),
            ),
        )

        return result

    def __init__(self, data=None, cchq_domain=None, cchq_is_previewer=False, *args, **kwargs):
        self._cchq_domain = cchq_domain
        self._cchq_is_previewer = cchq_is_previewer
        super(SettingsForm, self).__init__(data, *args, **kwargs)

        self.helper = HQFormHelper()

        self.helper.layout = crispy.Layout(
            *self.sections
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
    def enable_registration_welcome_sms_for_case(self):
        return (self.cleaned_data.get('registration_welcome_message') in
                (WELCOME_RECIPIENT_CASE, WELCOME_RECIPIENT_ALL))

    @property
    def enable_registration_welcome_sms_for_mobile_worker(self):
        return (self.cleaned_data.get('registration_welcome_message') in
                (WELCOME_RECIPIENT_MOBILE_WORKER, WELCOME_RECIPIENT_ALL))

    @property
    def current_values(self):
        current_values = {}
        for field_name in self.fields.keys():
            value = self[field_name].value()
            if field_name in ["restricted_sms_times_json",
                "sms_conversation_times_json"]:
                if isinstance(value, six.string_types):
                    soft_assert_type_text(value)
                    current_values[field_name] = json.loads(value)
                else:
                    current_values[field_name] = value
            elif field_name in ['sms_case_registration_owner_id', 'sms_case_registration_user_id']:
                if value:
                    obj = self.get_user_group_or_location(value)
                    if isinstance(obj, SQLLocation):
                        current_values[field_name] = {'id': value, 'text': _("Organization: {}").format(obj.name)}
                    elif isinstance(obj, Group):
                        current_values[field_name] = {'id': value, 'text': _("User Group: {}").format(obj.name)}
                    elif isinstance(obj, CommCareUser):
                        current_values[field_name] = {'id': value, 'text': _("User: {}").format(obj.raw_username)}
            else:
                current_values[field_name] = value
        return current_values

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

    def clean_count_messages_as_read_by_anyone(self):
        return (self.cleaned_data.get("count_messages_as_read_by_anyone")
            == ENABLED)

    def clean_sms_case_registration_enabled(self):
        return (self.cleaned_data.get("sms_case_registration_enabled")
            == ENABLED)

    def clean_sms_case_registration_type(self):
        return self._clean_dependent_field("sms_case_registration_enabled",
            "sms_case_registration_type")

    def get_user_group_or_location(self, object_id):
        try:
            return SQLLocation.active_objects.get(
                domain=self._cchq_domain,
                location_id=object_id,
                location_type__shares_cases=True,
            )
        except SQLLocation.DoesNotExist:
            pass

        try:
            group = Group.get(object_id)
            if group.doc_type == 'Group' and group.domain == self._cchq_domain and group.case_sharing:
                return group
        except ResourceNotFound:
            pass

        return self.get_user(object_id)

    def get_user(self, object_id):
        try:
            user = CommCareUser.get(object_id)
            if user.doc_type == 'CommCareUser' and user.domain == self._cchq_domain:
                return user
        except ResourceNotFound:
            pass

        return None

    def clean_sms_case_registration_owner_id(self):
        if not self.cleaned_data.get("sms_case_registration_enabled"):
            return None

        value = self.cleaned_data.get("sms_case_registration_owner_id")
        if not value:
            raise ValidationError(_("This field is required."))

        obj = self.get_user_group_or_location(value)
        if not isinstance(obj, (CommCareUser, Group, SQLLocation)):
            raise ValidationError(_("Please select again"))

        return value

    def clean_sms_case_registration_user_id(self):
        if not self.cleaned_data.get("sms_case_registration_enabled"):
            return None

        value = self.cleaned_data.get("sms_case_registration_user_id")
        if not value:
            raise ValidationError(_("This field is required."))

        obj = self.get_user(value)
        if not isinstance(obj, CommCareUser):
            raise ValidationError(_("Please select again"))

        return value

    def clean_sms_mobile_worker_registration_enabled(self):
        return (self.cleaned_data.get("sms_mobile_worker_registration_enabled")
                == ENABLED)

    def clean_sms_conversation_length(self):
        # Just cast to int, the ChoiceField will validate that it is an integer
        return int(self.cleaned_data.get("sms_conversation_length"))

    def clean_custom_daily_outbound_sms_limit(self):
        if not self._cchq_is_previewer:
            return None

        if self.cleaned_data.get('override_daily_outbound_sms_limit') != ENABLED:
            return None

        value = self.cleaned_data.get("custom_daily_outbound_sms_limit")
        if not value:
            raise ValidationError(_("This field is required"))

        return value


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
    inbound_api_key = CharField(
        required=False,
        label=ugettext_lazy("Inbound API Key"),
        disabled=True,
    )

    @property
    def is_global_backend(self):
        return self._cchq_domain is None

    @property
    def general_fields(self):
        fields = [
            crispy.Field('name', css_class='input-xxlarge'),
            crispy.Field('description', css_class='input-xxlarge', rows="3"),
            crispy.Field('reply_to_phone_number', css_class='input-xxlarge'),
        ]

        if not self.is_global_backend:
            fields.extend([
                crispy.Field(
                    twbscrispy.PrependedText(
                        'give_other_domains_access', '', data_bind="checked: share_backend"
                    )
                ),
                crispy.Div(
                    'authorized_domains',
                    data_bind="visible: showAuthorizedDomains",
                ),
            ])

        if self._cchq_backend_id:
            backend = SQLMobileBackend.load(self._cchq_backend_id)
            if backend.show_inbound_api_key_during_edit:
                self.fields['inbound_api_key'].initial = backend.inbound_api_key
                fields.append(crispy.Field('inbound_api_key'))

        return fields

    def __init__(self, *args, **kwargs):
        button_text = kwargs.pop('button_text', _("Create SMS Gateway"))
        self._cchq_domain = kwargs.pop('domain')
        self._cchq_backend_id = kwargs.pop('backend_id')
        super(BackendForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('General Settings'),
                *self.general_fields
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
            hqcrispy.FormActions(
                StrictButton(
                    button_text,
                    type="submit",
                    css_class='btn-primary'
                ),
            ),
        )

        if self._cchq_backend_id:
            #   When editing, don't allow changing the name because name might be
            # referenced as a contact-level backend preference.
            #   By setting disabled to True, Django makes sure the value won't change
            # even if something else gets posted.
            self.fields['name'].disabled = True

    @property
    def gateway_specific_fields(self):
        return crispy.Div()

    def clean_name(self):
        value = self.cleaned_data.get("name")
        if value is not None:
            value = value.strip().upper()
        if value is None or value == "":
            raise ValidationError(_("This field is required."))
        if re.compile(r"\s").search(value) is not None:
            raise ValidationError(_("Name may not contain any spaces."))

        if self.is_global_backend:
            # We're using the form to create a global backend, so
            # ensure name is not duplicated among other global backends
            is_unique = SQLMobileBackend.name_is_unique(
                value,
                backend_id=self._cchq_backend_id
            )
        else:
            # We're using the form to create a domain-level backend, so
            # ensure name is not duplicated among other backends owned by this domain
            is_unique = SQLMobileBackend.name_is_unique(
                value,
                domain=self._cchq_domain,
                backend_id=self._cchq_backend_id
            )

        if not is_unique:
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
    catchall_backend_id = ChoiceField(
        label=ugettext_lazy("Catch-All Gateway"),
        required=False
    )
    backend_map = CharField(required=False)

    def __init__(self, *args, **kwargs):
        backends = kwargs.pop('backends')
        super(BackendMapForm, self).__init__(*args, **kwargs)
        self.set_catchall_choices(backends)
        self.setup_crispy()

    def set_catchall_choices(self, backends):
        backend_choices = [('', _("(none)"))]
        backend_choices.extend([
            (backend.pk, backend.name) for backend in backends
        ])
        self.fields['catchall_backend_id'].choices = backend_choices

    def setup_crispy(self):
        self.helper = HQFormHelper()
        self.helper.form_method = 'POST'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Default Gateways"),
                hqcrispy.B3MultiField(
                    _("Default Gateway by Prefix"),
                    hqcrispy.ErrorsOnlyField('backend_map'),
                    crispy.Div(
                        data_bind="template: {"
                                  " name: 'ko-template-backend-map', "
                                  " data: $data"
                                  "}"
                    ),
                ),
                'catchall_backend_id',
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _("Save"),
                    type="submit",
                    css_class='btn-primary'
                ),
            ),
        )

    def _clean_prefix(self, prefix):
        try:
            prefix = int(prefix)
            if prefix <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError(_("Please enter a positive number for the prefix."))

        return str(prefix)

    def _clean_backend_id(self, backend_id):
        try:
            backend_id = int(backend_id)
        except (ValueError, TypeError):
            raise ValidationError(_("Invalid Backend Specified."))

        try:
            backend = SQLMobileBackend.load(backend_id)
        except:
            raise ValidationError(_("Invalid Backend Specified."))

        if (
            backend.deleted or
            not backend.is_global or
            backend.backend_type != SQLMobileBackend.SMS
        ):
            raise ValidationError(_("Invalid Backend Specified."))

        return backend_id

    def clean_backend_map(self):
        value = self.cleaned_data.get('backend_map')
        try:
            value = json.loads(value)
        except:
            raise ValidationError(_("An unexpected error occurred. Please reload and try again"))

        cleaned_value = {}
        for mapping in value:
            prefix = self._clean_prefix(mapping.get('prefix'))
            if prefix in cleaned_value:
                raise ValidationError(_("Prefix is specified twice: %s") % prefix)

            cleaned_value[prefix] = self._clean_backend_id(mapping.get('backend_id'))
        return cleaned_value

    def clean_catchall_backend_id(self):
        value = self.cleaned_data.get('catchall_backend_id')
        if not value:
            return None

        return self._clean_backend_id(value)


class SendRegistrationInvitationsForm(Form):

    PHONE_TYPE_ANDROID_ONLY = 'ANDROID'
    PHONE_TYPE_ANY = 'ANY'

    PHONE_CHOICES = (
        (PHONE_TYPE_ANDROID_ONLY, ugettext_lazy("Android Only")),
        (PHONE_TYPE_ANY, ugettext_lazy("Android or Other")),
    )

    phone_numbers = TrimmedCharField(
        label=ugettext_lazy("Phone Number(s)"),
        required=True,
        widget=forms.Textarea,
    )

    app_id = ChoiceField(
        label=ugettext_lazy("Application"),
        required=True,
    )

    action = CharField(
        initial='invite',
        widget=forms.HiddenInput(),
    )

    registration_message_type = ChoiceField(
        required=True,
        choices=DEFAULT_CUSTOM_CHOICES,
    )

    custom_registration_message = TrimmedCharField(
        label=ugettext_lazy("Registration Message"),
        required=False,
        widget=forms.Textarea,
    )

    phone_type = ChoiceField(
        label=ugettext_lazy("Recipient phones are"),
        required=True,
        choices=PHONE_CHOICES,
    )

    make_email_required = ChoiceField(
        label=ugettext_lazy("Make email required at registration"),
        required=True,
        choices=ENABLED_DISABLED_CHOICES,
    )

    @property
    def android_only(self):
        return self.cleaned_data.get('phone_type') == self.PHONE_TYPE_ANDROID_ONLY

    @property
    def require_email(self):
        return self.cleaned_data.get('make_email_required') == ENABLED

    def set_app_id_choices(self):
        app_ids = get_built_app_ids(self.domain)
        choices = []
        for app_doc in iter_docs(Application.get_db(), app_ids):
            # This will return both Application and RemoteApp docs, but
            # they both have a name attribute
            choices.append((app_doc['_id'], app_doc['name']))
        choices.sort(key=lambda x: x[1])
        self.fields['app_id'].choices = choices

    def __init__(self, *args, **kwargs):
        if 'domain' not in kwargs:
            raise Exception('Expected kwargs: domain')
        self.domain = kwargs.pop('domain')

        super(SendRegistrationInvitationsForm, self).__init__(*args, **kwargs)
        self.set_app_id_choices()

        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Div(
                'app_id',
                crispy.Field(
                    'phone_numbers',
                    placeholder=_("Enter phone number(s) in international "
                        "format. Example: +27..., +91...,"),
                ),
                'phone_type',
                InlineField('action'),
                css_class='modal-body',
            ),
            hqcrispy.FieldsetAccordionGroup(
                _("Advanced"),
                crispy.Field(
                    'registration_message_type',
                    data_bind='value: registration_message_type',
                ),
                crispy.Div(
                    crispy.Field(
                        'custom_registration_message',
                        placeholder=_("Enter registration SMS"),
                    ),
                    data_bind='visible: showCustomRegistrationMessage',
                ),
                'make_email_required',
                active=False
            ),
            crispy.Div(
                twbscrispy.StrictButton(
                    _("Cancel"),
                    data_dismiss='modal',
                    css_class="btn btn-default",
                ),
                twbscrispy.StrictButton(
                    _("Send Invitation"),
                    type="submit",
                    css_class="btn btn-primary",
                ),
                css_class='modal-footer',
            ),
        )

    def clean_phone_numbers(self):
        value = self.cleaned_data.get('phone_numbers', '')
        phone_list = [strip_plus(s.strip()) for s in value.split(',')]
        phone_list = [phone for phone in phone_list if phone]
        if len(phone_list) == 0:
            raise ValidationError(_("This field is required."))
        for phone_number in phone_list:
            validate_phone_number(phone_number)
        return list(set(phone_list))

    def clean_custom_registration_message(self):
        value = self.cleaned_data.get('custom_registration_message')
        if self.cleaned_data.get('registration_message_type') == CUSTOM:
            if not value:
                raise ValidationError(_("Please enter a message"))
            return value

        return None


class InitiateAddSMSBackendForm(Form):
    action = CharField(
        initial='new_backend',
        widget=forms.HiddenInput(),
    )
    hq_api_id = ChoiceField(
        required=False,
        label="Gateway Type",
    )

    def __init__(self, is_superuser=False, *args, **kwargs):
        super(InitiateAddSMSBackendForm, self).__init__(*args, **kwargs)

        from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
        backend_classes = get_sms_backend_classes()
        backend_choices = []
        for api_id, klass in backend_classes.items():
            if is_superuser or api_id == SQLTelerivetBackend.get_api_id():
                friendly_name = klass.get_generic_name()
                backend_choices.append((api_id, friendly_name))
        backend_choices = sorted(backend_choices, key=lambda backend: backend[1])
        self.fields['hq_api_id'].choices = backend_choices

        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            hqcrispy.B3MultiField(
                _("Create Another Gateway"),
                InlineField('action'),
                Div(InlineField('hq_api_id', css_class="ko-select2"), css_class='col-sm-6 col-md-6 col-lg-4'),
                Div(StrictButton(
                    mark_safe('<i class="fa fa-plus"></i> Add Another Gateway'),
                    css_class='btn-primary',
                    type='submit',
                    style="margin-left:5px;"
                ), css_class='col-sm-3 col-md-2 col-lg-2'),
            ),
        )


class SubscribeSMSForm(Form):
    stock_out_facilities = BooleanField(
        label=ugettext_lazy("Receive stockout facilities SMS alert"),
        required=False,
        help_text=ugettext_lazy(
            "This will alert you with specific users/facilities that are "
            "stocked out of your commodities"
        )
    )
    stock_out_commodities = BooleanField(
        label=ugettext_lazy("Receive stockout commodities SMS alert"),
        required=False,
        help_text=ugettext_lazy(
            "This will alert you with specific commodities that are stocked "
            "out by your users/facilities"
        )
    )
    stock_out_rates = BooleanField(
        label=ugettext_lazy("Receive stockout SMS alert"),
        required=False,
        help_text=ugettext_lazy(
            "This will alert you with the percent of facilities that are "
            "stocked out of a specific commodity"
        )
    )
    non_report = BooleanField(
        label=ugettext_lazy("Receive non-reporting SMS alert"),
        required=False,
        help_text=ugettext_lazy(
            "This alert highlight users/facilities which have not submitted "
            "their CommCare Supply stock report."
        )
    )

    def __init__(self, *args, **kwargs):
        super(SubscribeSMSForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Subscribe settings'),
                twbscrispy.PrependedText('stock_out_facilities', ''),
                twbscrispy.PrependedText('stock_out_commodities', ''),
                twbscrispy.PrependedText('stock_out_rates', ''),
                twbscrispy.PrependedText('non_report', '')
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Update settings"),
                    type="submit",
                    css_class="btn-primary",
                ),
            )
        )

    def save(self, commtrack_settings):
        alert_config = commtrack_settings.alert_config
        alert_config.stock_out_facilities = self.cleaned_data.get("stock_out_facilities", False)
        alert_config.stock_out_commodities = self.cleaned_data.get("stock_out_commodities", False)
        alert_config.stock_out_rates = self.cleaned_data.get("stock_out_rates", False)
        alert_config.non_report = self.cleaned_data.get("non_report", False)

        commtrack_settings.save()


class ComposeMessageForm(forms.Form):

    recipients = forms.CharField(widget=forms.Textarea,
                                 help_text=ugettext_lazy("Type a username, group name or 'send to all'"))
    message = forms.CharField(widget=forms.Textarea, help_text=ugettext_lazy('0 characters (160 max)'))

    def __init__(self, *args, **kwargs):
        domain = kwargs.pop('domain')
        super(ComposeMessageForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.form_action = reverse('send_to_recipients', args=[domain])
        self.helper.layout = crispy.Layout(
            crispy.Field('recipients', rows=2, css_class='sms-typeahead'),
            crispy.Field('message', rows=2),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Send Message"),
                    type="submit",
                    css_class="btn-primary",
                ),
            ),
        )
