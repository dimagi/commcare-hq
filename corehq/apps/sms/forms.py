import copy
import json
import re

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    IntegerField,
)
from django.forms.forms import Form
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from couchdbkit.exceptions import ResourceNotFound
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import InlineField, StrictButton
from crispy_forms.layout import Div

from dimagi.utils.django.fields import TrimmedCharField

from corehq import toggles
from corehq.apps.commtrack.models import AlertConfig
from corehq.apps.domain.models import DayTimeWindow
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.hqwebapp.fields import MultiEmailField
from corehq.apps.hqwebapp.widgets import SelectToggle
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.forms import validate_time
from corehq.apps.sms.mixin import BadSMSConfigException
from corehq.apps.sms.models import SQLMobileBackend
from corehq.apps.sms.util import (
    ALLOWED_SURVEY_DATE_FORMATS,
    clean_phone_number,
    get_sms_backend_classes,
    is_superuser_or_contractor,
    validate_phone_number,
)
from corehq.apps.users.models import CommCareUser, CouchUser

ENABLED = "ENABLED"
DISABLED = "DISABLED"

ENABLED_DISABLED_CHOICES = (
    (DISABLED, gettext_noop("Disabled")),
    (ENABLED, gettext_noop("Enabled")),
)

DEFAULT = "DEFAULT"
CUSTOM = "CUSTOM"

DEFAULT_CUSTOM_CHOICES = (
    (DEFAULT, gettext_noop("Default")),
    (CUSTOM, gettext_noop("Custom")),
)

MESSAGE_COUNTER_CHOICES = (
    (DEFAULT, gettext_noop("Don't use counter")),
    (CUSTOM, gettext_noop("Use counter with threshold:")),
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
    (WELCOME_RECIPIENT_NONE, gettext_lazy('Nobody')),
    (WELCOME_RECIPIENT_CASE, gettext_lazy('Cases only')),
    (WELCOME_RECIPIENT_MOBILE_WORKER, gettext_lazy('Mobile Workers only')),
    (WELCOME_RECIPIENT_ALL, gettext_lazy('Cases and Mobile Workers')),
)

LANGUAGE_FALLBACK_NONE = 'NONE'
LANGUAGE_FALLBACK_SCHEDULE = 'SCHEDULE'
LANGUAGE_FALLBACK_DOMAIN = 'DOMAIN'
LANGUAGE_FALLBACK_UNTRANSLATED = 'UNTRANSLATED'

LANGUAGE_FALLBACK_CHOICES = (
    (LANGUAGE_FALLBACK_NONE, gettext_lazy("""
        Only send message if text is available in recipient's preferred language
    """)),
    (LANGUAGE_FALLBACK_SCHEDULE, gettext_lazy("""
        Use text from the alert or broadcast's default language as a backup
    """)),
    (LANGUAGE_FALLBACK_DOMAIN, gettext_lazy("""
        Use text from the project's default language as a backup
        if the alert or broadcast's language is also unavailable
    """)),
    (LANGUAGE_FALLBACK_UNTRANSLATED, gettext_lazy("""
        Use all available text backups, including untranslated content
    """)),
)


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
            self.validate_phone_number(phone_number)

        return result

    def validate_phone_number(self, phone_number: str) -> None:
        validate_phone_number(phone_number)


class SettingsForm(Form):
    # General Settings
    use_default_sms_response = ChoiceField(
        required=False,
        label=gettext_noop("Default SMS Response"),
        choices=ENABLED_DISABLED_CHOICES,
    )
    default_sms_response = TrimmedCharField(
        required=False,
        label="",
    )
    use_restricted_sms_times = ChoiceField(
        required=False,
        label=gettext_noop("Send SMS on..."),
        choices=(
            (DISABLED, gettext_noop("any day, at any time")),
            (ENABLED, gettext_noop("only specific days and times")),
        ),
    )
    restricted_sms_times_json = CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    sms_survey_date_format = ChoiceField(
        required=False,
        label=gettext_lazy("SMS Survey Date Format"),
        choices=(
            (df.human_readable_format, gettext_lazy(df.human_readable_format))
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
        label=gettext_noop("Enter a Case Property"),
    )
    use_custom_message_count_threshold = ChoiceField(
        required=False,
        choices=MESSAGE_COUNTER_CHOICES,
    )
    custom_message_count_threshold = IntegerField(
        required=False,
        label=gettext_noop("Enter a Number"),
    )
    use_sms_conversation_times = ChoiceField(
        required=False,
        label=gettext_noop("Delay Automated SMS"),
        choices=ENABLED_DISABLED_CHOICES,
        widget=SelectToggle(choices=ENABLED_DISABLED_CHOICES, attrs={"ko_value": "use_sms_conversation_times"}),
    )
    sms_conversation_times_json = CharField(
        required=False,
        widget=forms.HiddenInput,
    )
    sms_conversation_length = ChoiceField(
        required=False,
        label=gettext_noop("Conversation Duration"),
        choices=SMS_CONVERSATION_LENGTH_CHOICES,
    )
    survey_traffic_option = ChoiceField(
        required=False,
        label=gettext_noop("Survey Traffic"),
        choices=(
            (SHOW_ALL, gettext_noop("Show all survey traffic")),
            (SHOW_INVALID, gettext_noop("Hide all survey traffic except "
                                        "invalid responses")),
            (HIDE_ALL, gettext_noop("Hide all survey traffic")),
        ),
    )
    count_messages_as_read_by_anyone = ChoiceField(
        required=False,
        label=gettext_noop("A Message is Read..."),
        choices=(
            (ENABLED, gettext_noop("when it is read by anyone")),
            (DISABLED, gettext_noop("only for the user that reads it")),
        ),
    )
    use_custom_chat_template = ChoiceField(
        required=False,
        choices=DEFAULT_CUSTOM_CHOICES,
    )
    custom_chat_template = TrimmedCharField(
        required=False,
        label=gettext_noop("Enter Chat Template Identifier"),
    )

    # Registration settings
    sms_case_registration_enabled = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=gettext_noop("Case Self-Registration"),
    )
    sms_case_registration_type = TrimmedCharField(
        required=False,
        label=gettext_noop("Default Case Type"),
    )
    sms_case_registration_owner_id = CharField(
        required=False,
        label=gettext_noop("Default Case Owner"),
        widget=forms.Select(choices=[]),
    )
    sms_case_registration_user_id = CharField(
        required=False,
        label=gettext_noop("Registration Submitter"),
        widget=forms.Select(choices=[]),
    )
    sms_mobile_worker_registration_enabled = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=gettext_noop("SMS Mobile Worker Registration"),
    )
    sms_worker_registration_alert_emails = MultiEmailField(
        required=False,
        label=gettext_noop("Emails to send alerts for new mobile worker registrations"),
    )
    registration_welcome_message = ChoiceField(
        choices=WELCOME_RECIPIENT_CHOICES,
        label=gettext_lazy("Send registration welcome message to"),
    )
    language_fallback = ChoiceField(
        choices=LANGUAGE_FALLBACK_CHOICES,
        label=gettext_lazy("Backup behavior for missing translations"),
    )
    twilio_whatsapp_phone_number = CharField(
        required=False,
    )

    # Internal settings
    override_daily_outbound_sms_limit = ChoiceField(
        required=False,
        choices=ENABLED_DISABLED_CHOICES,
        label=gettext_lazy("Override Daily Outbound SMS Limit"),
    )
    custom_daily_outbound_sms_limit = IntegerField(
        required=False,
        label=gettext_noop("Daily Outbound SMS Limit"),
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
                data_bind="value: sms_mobile_worker_registration_enabled",
            ),
            crispy.Div(
                hqcrispy.FieldWithHelpBubble(
                    "sms_worker_registration_alert_emails",
                    help_bubble_text=_("Email these people when new users register through SMS"),
                ),
                data_bind="visible: showAdminAlertEmails",
            ),
            hqcrispy.FieldWithHelpBubble(
                'registration_welcome_message',
                help_bubble_text=_("Choose whether to send an automatic "
                    "welcome message to cases, mobile workers, or both, "
                    "after they self-register. The welcome message can be "
                    "configured in the SMS languages and translations page "
                    "(Messaging -> Languages -> Messaging Translations)."),
            ),
            hqcrispy.FieldWithHelpBubble(
                'language_fallback',
                help_bubble_text=_("""
                    Choose what should happen when a broadcast or alert should be sent to a recipient but no
                    translations exists in the user's preferred language. You may choose not to send a message in
                    that case, or to try one of several backups.<br><br>The first backup uses the broadcast or
                    alert's default language. If that translation is also unavailable, the second backup is text in
                    the project's default SMS language. If that translation is also unavailable, you may choose
                    to use untranslated text, if there is any.
                """),
            ),
        ]

        if toggles.WHATSAPP_MESSAGING.enabled(self.domain):
            fields.append(hqcrispy.FieldWithHelpBubble(
                'twilio_whatsapp_phone_number',
                help_bubble_text=_("""
                    Whatsapp-enabled phone number for use with Twilio.
                    This should be formatted as a full-length, numeric-only
                    phone number, e.g., 16173481000.
                """),
            ))

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

        if self.is_previewer:
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

    def __init__(self, data=None, domain=None, is_previewer=False, *args, **kwargs):
        self.domain = domain
        self.is_previewer = is_previewer
        super(SettingsForm, self).__init__(data, *args, **kwargs)

        self.helper = HQFormHelper()

        self.helper.layout = crispy.Layout(
            *self.sections
        )
        self.set_admin_email_choices(data, kwargs)

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

    def set_admin_email_choices(self, data, kwargs):
        email_choices = []
        if 'initial' in kwargs and 'sms_worker_registration_alert_emails' in kwargs['initial']:
            # for a GET request, the form is populated by 'initial'
            email_choices = kwargs['initial']['sms_worker_registration_alert_emails']
        if data:
            # for a POST request, we should return the list of emails that was given
            email_choices = data.getlist('sms_worker_registration_alert_emails')

        self.fields['sms_worker_registration_alert_emails'].choices = [
            (email, email) for email in email_choices
        ]

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
            if field_name in ["restricted_sms_times_json", "sms_conversation_times_json"]:
                if isinstance(value, str):
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
        if not self.is_previewer:
            return None
        return self.cleaned_data.get("use_custom_chat_template") == CUSTOM

    def clean_custom_chat_template(self):
        if not self.is_previewer:
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
                domain=self.domain,
                location_id=object_id,
                location_type__shares_cases=True,
            )
        except SQLLocation.DoesNotExist:
            pass

        try:
            group = Group.get(object_id)
            if group.doc_type == 'Group' and group.domain == self.domain and group.case_sharing:
                return group
            elif group.is_deleted:
                return None
        except ResourceNotFound:
            pass

        return self.get_user(object_id)

    def get_user(self, object_id):
        try:
            user = CommCareUser.get(object_id)
            if user.doc_type == 'CommCareUser' and user.domain == self.domain:
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
        if not self.is_previewer:
            return None

        if self.cleaned_data.get('override_daily_outbound_sms_limit') != ENABLED:
            return None

        value = self.cleaned_data.get("custom_daily_outbound_sms_limit")
        if not value:
            raise ValidationError(_("This field is required"))

        return value


class BackendForm(Form):
    domain = None
    backend_id = None
    name = CharField(
        label=gettext_noop("Name")
    )
    display_name = CharField(
        label=gettext_noop("Display Name"),
        required=False,
    )
    description = CharField(
        label=gettext_noop("Description"),
        widget=forms.Textarea(attrs={"class": "vertical-resize"}),
        required=False,
    )
    give_other_domains_access = BooleanField(
        required=False,
        label=gettext_noop("Give other domains access.")
    )
    authorized_domains = CharField(
        required=False,
        label=gettext_noop("List of authorized domains"),
        help_text=gettext_lazy("A comma-separated list of domain names")
    )
    reply_to_phone_number = CharField(
        required=False,
        label=gettext_noop("Reply-To Phone Number"),
    )
    inbound_api_key = CharField(
        required=False,
        label=gettext_lazy("Inbound API Key"),
        disabled=True,
    )
    opt_out_keywords = CharField(
        required=False,
        label=gettext_noop("List of opt out keywords"),
        help_text=gettext_lazy("A comma-separated list of keywords")
    )
    opt_in_keywords = CharField(
        required=False,
        label=gettext_noop("List of opt in keywords"),
        help_text=gettext_lazy("A comma-separated list of keywords")
    )

    @property
    def is_global_backend(self):
        return self.domain is None

    @property
    def general_fields(self):
        fields = [
            crispy.Field('name', css_class='input-xxlarge'),
            crispy.Field('display_name', css_class='input-xxlarge'),
            crispy.Field('description', css_class='input-xxlarge', rows="3"),
            crispy.Field('reply_to_phone_number', css_class='input-xxlarge'),
            crispy.Field('opt_out_keywords'),
            crispy.Field('opt_in_keywords')
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

        if self.backend_id:
            backend = SQLMobileBackend.load(self.backend_id)
            if backend.show_inbound_api_key_during_edit:
                self.fields['inbound_api_key'].initial = backend.inbound_api_key
                fields.append(crispy.Field('inbound_api_key'))

        return fields

    def __init__(self, *args, **kwargs):
        button_text = kwargs.pop('button_text', _("Create SMS Gateway"))
        self.domain = kwargs.pop('domain')
        self.backend_id = kwargs.pop('backend_id')
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

        if self.backend_id:
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
                backend_id=self.backend_id
            )
        else:
            # We're using the form to create a domain-level backend, so
            # ensure name is not duplicated among other backends owned by this domain
            is_unique = SQLMobileBackend.name_is_unique(
                value,
                domain=self.domain,
                backend_id=self.backend_id
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

    def clean_opt_out_keywords(self):
        keywords = self.cleaned_data.get('opt_out_keywords')
        if not keywords:
            return []
        else:
            return [kw.strip().upper() for kw in keywords.split(',')]

    def clean_opt_in_keywords(self):
        keywords = self.cleaned_data.get('opt_in_keywords')
        if not keywords:
            return []
        else:
            return [kw.strip().upper() for kw in keywords.split(',')]

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
        label=gettext_lazy("Catch-All Gateway"),
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
        except:  # noqa: E722
            raise ValidationError(_("Invalid Backend Specified."))

        if (
            backend.deleted
            or not backend.is_global
            or backend.backend_type != SQLMobileBackend.SMS
        ):
            raise ValidationError(_("Invalid Backend Specified."))

        return backend_id

    def clean_backend_map(self):
        value = self.cleaned_data.get('backend_map')
        try:
            value = json.loads(value)
        except:  # noqa: E722
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


class InitiateAddSMSBackendForm(Form):
    action = CharField(
        initial='new_backend',
        widget=forms.HiddenInput(),
    )
    hq_api_id = ChoiceField(
        required=False,
        label="Gateway Type",
    )

    def __init__(self, user: CouchUser, *args, **kwargs):
        domain = kwargs.pop('domain', None)
        super(InitiateAddSMSBackendForm, self).__init__(*args, **kwargs)

        from corehq.messaging.smsbackends.telerivet.models import (
            SQLTelerivetBackend,
        )
        backend_classes = self.backend_classes_for_domain(domain)

        backend_choices = []
        for api_id, klass in backend_classes.items():
            if is_superuser_or_contractor(user) or api_id == SQLTelerivetBackend.get_api_id():
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
                    mark_safe('<i class="fa fa-plus"></i> Add Another Gateway'),  # nosec: no user input
                    css_class='btn-primary',
                    type='submit',
                    style="margin-left:5px;"
                ), css_class='col-sm-3 col-md-2 col-lg-2'),
            ),
        )

    def backend_classes_for_domain(self, domain):
        backends = copy.deepcopy(get_sms_backend_classes())
        if (domain is not None) and (not toggles.TURN_IO_BACKEND.enabled(domain)):
            backends.pop('TURN')

        return backends


class SubscribeSMSForm(Form):
    stock_out_facilities = BooleanField(
        label=gettext_lazy("Receive stockout facilities SMS alert"),
        required=False,
        help_text=gettext_lazy(
            "This will alert you with specific users/facilities that are "
            "stocked out of your commodities"
        )
    )
    stock_out_commodities = BooleanField(
        label=gettext_lazy("Receive stockout commodities SMS alert"),
        required=False,
        help_text=gettext_lazy(
            "This will alert you with specific commodities that are stocked "
            "out by your users/facilities"
        )
    )
    stock_out_rates = BooleanField(
        label=gettext_lazy("Receive stockout SMS alert"),
        required=False,
        help_text=gettext_lazy(
            "This will alert you with the percent of facilities that are "
            "stocked out of a specific commodity"
        )
    )
    non_report = BooleanField(
        label=gettext_lazy("Receive non-reporting SMS alert"),
        required=False,
        help_text=gettext_lazy(
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
        if not hasattr(commtrack_settings, 'alertconfig'):
            commtrack_settings.alertconfig = AlertConfig()

        alert_config = commtrack_settings.alertconfig
        alert_config.stock_out_facilities = self.cleaned_data.get("stock_out_facilities", False)
        alert_config.stock_out_commodities = self.cleaned_data.get("stock_out_commodities", False)
        alert_config.stock_out_rates = self.cleaned_data.get("stock_out_rates", False)
        alert_config.non_report = self.cleaned_data.get("non_report", False)

        alert_config.commtrack_settings = commtrack_settings
        alert_config.save()


class ComposeMessageForm(forms.Form):
    recipients = forms.MultipleChoiceField(
        widget=forms.SelectMultiple(attrs={'class': 'hqwebapp-select2'}),
    )
    message = forms.CharField(widget=forms.Textarea(attrs={"class": "vertical-resize"}),
    help_text=gettext_lazy('0 characters (160 max)'))

    def __init__(self, *args, **kwargs):
        domain = kwargs.pop('domain')
        super(ComposeMessageForm, self).__init__(*args, **kwargs)

        from corehq.apps.sms.views import get_sms_autocomplete_context
        self.fields['recipients'].choices = [
            (contact, contact) for contact in get_sms_autocomplete_context(domain)
        ]

        self.helper = HQFormHelper()
        self.helper.form_action = reverse('send_to_recipients', args=[domain])
        self.helper.layout = crispy.Layout(
            crispy.Field('recipients'),
            crispy.Field('message', rows=2),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    _("Send Message"),
                    type="submit",
                    css_class="btn-primary",
                ),
            ),
        )


class SentTestSmsForm(Form):
    phone_number = CharField(
        required=True, help_text=gettext_lazy("Phone number with country code"))
    message = CharField(widget=forms.Textarea(attrs={"class": "vertical-resize"}), required=True)
    backend_id = ChoiceField(
        label=gettext_lazy("Gateway"),
        required=False
    )
    claim_channel = BooleanField(
        label=gettext_lazy("Attempt to claim the channel for this number."),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        backends = kwargs.pop('backends')
        self.domain = kwargs.pop('domain')
        super(SentTestSmsForm, self).__init__(*args, **kwargs)
        self.set_backend_choices(backends)
        self.setup_crispy()

    def set_backend_choices(self, backends):
        backend_choices = [('', _("(none)"))]
        backend_choices.extend([
            (backend.couch_id, backend.name) for backend in backends
        ])
        self.fields['backend_id'].choices = backend_choices

    def setup_crispy(self):
        fields = [
            crispy.Field('phone_number'),
            crispy.Field('message', rows=2),
            crispy.Field('backend_id'),
        ]
        if toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(self.domain):
            fields.append(hqcrispy.FieldWithHelpBubble(
                "claim_channel",
                help_bubble_text=_("Use this option if the phone number is used by multiple projects "
                                   "and is currently claimed by another project or the default owner of "
                                   "the number is a different project."),
            ))
        fields.append(hqcrispy.FormActions(
            twbscrispy.StrictButton(
                _("Send Message"),
                type="submit",
                css_class="btn-primary",
            ),
        ))
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(*fields)

    def clean_phone_number(self):
        phone_number = clean_phone_number(self.cleaned_data['phone_number'])
        validate_phone_number(phone_number)
        return phone_number

    def clean_backend_id(self):
        backend_id = self.cleaned_data['backend_id']
        try:
            backend = SQLMobileBackend.load(backend_id, is_couch_id=True)
        except (BadSMSConfigException, SQLMobileBackend.DoesNotExist):
            backend = None

        if not backend or not backend.domain_is_authorized(self.domain):
            raise ValidationError("Invalid backend choice")

        return backend.couch_id
